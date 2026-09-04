import hmac
import hashlib
import json
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database.models.user import User
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.webhook_event import WebhookEvent
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.payment_attempt import PaymentAttempt
from app.services.authorization_service import AuthorizationService
from app.payments.utils import to_minor_units
from app.payments.provider import (
    PaymentProvider,
    PaymentProviderError,
    PaymentTimeoutError,
    PaymentInvalidRequestError
)
from app.payments.razorpay_provider import RazorpayProvider
from app.payments.mock_provider import MockPaymentProvider
from app.payments.state_machine import PaymentState, PaymentStateMachine

# Singleton Mock Provider for tests/deterministic simulation
_mock_provider = MockPaymentProvider()

class PaymentService:
    """
    Central Payment Service.
    Orchestrates pre-payment authorization verification, provider dispatch, idempotency,
    attempt auditing, state transitions, and webhooks.
    """

    @staticmethod
    def get_provider() -> PaymentProvider:
        """
        Resolves the configured payment provider.
        Enforces Razorpay Test Mode when configured, otherwise falls back to MockPaymentProvider.
        """
        if settings.ENVIRONMENT == "test" or settings.PAYMENT_PROVIDER == "mock":
            return _mock_provider

        is_razorpay_configured = bool(
            settings.RAZORPAY_KEY_ID
            and settings.RAZORPAY_KEY_SECRET
            and not settings.RAZORPAY_KEY_ID.startswith("your_")
            and not "xxxx" in settings.RAZORPAY_KEY_ID
        )
        if (settings.PAYMENT_PROVIDER == "razorpay" or is_razorpay_configured) and settings.ENVIRONMENT != "test":
            return RazorpayProvider(
                key_id=settings.RAZORPAY_KEY_ID,
                key_secret=settings.RAZORPAY_KEY_SECRET,
                webhook_secret=settings.RAZORPAY_WEBHOOK_SECRET
            )
        return _mock_provider

    @staticmethod
    def get_mock_provider() -> MockPaymentProvider:
        return _mock_provider

    @staticmethod
    def create_payment_order(
        db: Session,
        merchant_id: str,
        purchase_intent_id: str,
        authorization_id: str,
        idempotency_key: str,
        expected_amount: Optional[Decimal] = None,
        expected_currency: Optional[str] = None,
        provider_override: Optional[PaymentProvider] = None,
        trace_id: Optional[str] = None
    ) -> PaymentTransaction:
        # 1. Idempotency Check: Existing transaction with (merchant_id, idempotency_key)
        existing = db.query(PaymentTransaction).filter(
            PaymentTransaction.merchant_id == merchant_id,
            PaymentTransaction.idempotency_key == idempotency_key
        ).first()

        if existing:
            # If the existing transaction is UNKNOWN, block further order creation until reconciled
            if existing.status == PaymentState.UNKNOWN:
                return existing
            return existing

        # 2. Strict Pre-Payment Authorization Validation
        is_valid, reason, auth = AuthorizationService.validate_authorization(
            db=db,
            authorization_id=authorization_id,
            merchant_id=merchant_id,
            expected_amount=expected_amount,
            expected_currency=expected_currency
        )
        if not is_valid or not auth:
            raise HTTPException(status_code=400, detail=f"Invalid Authorization: {reason}")

        if auth.purchase_intent_id != purchase_intent_id:
            raise HTTPException(
                status_code=400,
                detail=f"Authorization mismatch: Auth {authorization_id} is bound to Intent {auth.purchase_intent_id}, not {purchase_intent_id}."
            )

        # 3. Invariant: Check if an active UNKNOWN transaction already exists for this authorization
        unknown_tx = db.query(PaymentTransaction).filter(
            PaymentTransaction.authorization_id == authorization_id,
            PaymentTransaction.status == PaymentState.UNKNOWN
        ).first()
        if unknown_tx:
            raise HTTPException(
                status_code=409,
                detail=f"An active transaction ({unknown_tx.id}) for this authorization is in UNKNOWN state. Reconcile before attempting further payment operations."
            )

        # 4. Verify Authorization not already paid
        already_paid = db.query(PaymentTransaction).filter(
            PaymentTransaction.authorization_id == authorization_id,
            PaymentTransaction.status == PaymentState.CAPTURED
        ).first()
        if already_paid:
            raise HTTPException(status_code=400, detail="This transaction authorization has already been paid and captured.")

        # 5. Generate deterministic receipt reference
        receipt = f"rcpt_{purchase_intent_id[:8]}_{idempotency_key[:8]}"

        # Initialize PaymentTransaction in ORDER_CREATING state
        transaction = PaymentTransaction(
            merchant_id=merchant_id,
            purchase_intent_id=purchase_intent_id,
            authorization_id=authorization_id,
            amount=Decimal(str(auth.authorized_amount)),
            currency=auth.currency,
            status=PaymentState.ORDER_CREATING,
            idempotency_key=idempotency_key,
            receipt=receipt,
            attempt_count=1
        )
        db.add(transaction)
        try:
            db.commit()
            db.refresh(transaction)
        except IntegrityError:
            # Concurrent race caught by DB unique constraint
            db.rollback()
            existing_race = db.query(PaymentTransaction).filter(
                PaymentTransaction.merchant_id == merchant_id,
                PaymentTransaction.idempotency_key == idempotency_key
            ).first()
            if existing_race:
                return existing_race
            raise HTTPException(status_code=409, detail="Concurrent payment transaction conflict.")

        # 6. Amount unit conversion: Authoritative Decimal -> Minor Units
        amount_minor = to_minor_units(transaction.amount, transaction.currency)
        provider = provider_override or PaymentService.get_provider()
        provider_name = "razorpay" if isinstance(provider, RazorpayProvider) else "mock"

        notes = {
            "merchant_id": merchant_id,
            "purchase_intent_id": purchase_intent_id,
            "authorization_id": authorization_id,
            "payment_transaction_id": transaction.id
        }
        request_fingerprint = hashlib.sha256(
            json.dumps({"amount": amount_minor, "currency": transaction.currency, "receipt": receipt, "notes": notes}, sort_keys=True).encode("utf-8")
        ).hexdigest()

        # 7. Record PaymentAttempt audit entry (STARTED)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        attempt = PaymentAttempt(
            merchant_id=merchant_id,
            payment_transaction_id=transaction.id,
            attempt_number=1,
            provider=provider_name,
            operation="CREATE_ORDER",
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            status="STARTED",
            trace_id=trace_id or idempotency_key,
            started_at=now
        )
        db.add(attempt)
        db.commit()

        # 8. Gateway Order Creation Call
        try:
            order_res = provider.create_order(
                amount_minor=amount_minor,
                currency=transaction.currency,
                receipt=receipt,
                notes=notes
            )
            transaction.razorpay_order_id = order_res.order_id
            PaymentStateMachine.transition(transaction, PaymentState.ORDER_CREATED, db=db)
            
            attempt.status = "SUCCESS"
            attempt.provider_order_id = order_res.order_id
            attempt.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        except PaymentTimeoutError as e:
            # Case A: Ambiguous timeout -> UNKNOWN
            PaymentStateMachine.transition(
                transaction,
                PaymentState.UNKNOWN,
                reason=str(e),
                error_code="GATEWAY_TIMEOUT",
                db=db
            )
            attempt.status = "TIMEOUT"
            attempt.error_code = "GATEWAY_TIMEOUT"
            attempt.error_message = str(e)
            attempt.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        except PaymentInvalidRequestError as e:
            # Case C: Definite client 4xx rejection before order creation -> FAILED
            PaymentStateMachine.transition(
                transaction,
                PaymentState.FAILED,
                reason=str(e),
                error_code="INVALID_GATEWAY_REQUEST",
                db=db
            )
            attempt.status = "FAILED"
            attempt.error_code = "INVALID_GATEWAY_REQUEST"
            attempt.error_message = str(e)
            attempt.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        except PaymentProviderError as e:
            PaymentStateMachine.transition(
                transaction,
                PaymentState.FAILED,
                reason=e.message,
                error_code=e.code,
                db=db
            )
            attempt.status = "FAILED"
            attempt.error_code = e.code
            attempt.error_message = e.message
            attempt.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        except Exception as e:
            PaymentStateMachine.transition(
                transaction,
                PaymentState.UNKNOWN,
                reason=str(e),
                error_code="UNEXPECTED_ERROR",
                db=db
            )
            attempt.status = "UNKNOWN"
            attempt.error_code = "UNEXPECTED_ERROR"
            attempt.error_message = str(e)
        db.commit()
        db.refresh(transaction)

        # Audit Event for Payment Order Creation Outcome
        from app.services.audit_service import AuditService
        intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == purchase_intent_id).first()
        assigned_trace = trace_id or (intent.trace_id if intent else f"trc_{transaction.id[:8]}")

        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=assigned_trace,
            session_id=intent.session_id if intent else None,
            purchase_intent_id=purchase_intent_id,
            authorization_id=authorization_id,
            payment_transaction_id=transaction.id,
            payment_attempt_id=attempt.id,
            actor_type="PROVIDER",
            action="CREATE_PAYMENT_ORDER",
            event_type="PAYMENT_ORDER_CREATED",
            previous_state=PaymentState.ORDER_CREATING,
            new_state=transaction.status,
            status="SUCCESS" if transaction.status == PaymentState.ORDER_CREATED else "TIMEOUT" if transaction.status == PaymentState.UNKNOWN else "FAILED",
            error_code=transaction.failure_code,
            reason=transaction.failure_message,
            metadata_json={
                "amount": str(transaction.amount),
                "currency": transaction.currency,
                "provider_order_id": transaction.razorpay_order_id,
                "idempotency_key": idempotency_key
            }
        )
        db.commit()
        db.refresh(transaction)
        return transaction

    @staticmethod
    def get_payment_transaction(db: Session, transaction_id: str, merchant_id: str) -> PaymentTransaction:
        tx = db.query(PaymentTransaction).filter(
            PaymentTransaction.id == transaction_id,
            PaymentTransaction.merchant_id == merchant_id
        ).first()
        if not tx:
            raise HTTPException(status_code=404, detail="Payment transaction not found for this merchant.")
        return tx

    @staticmethod
    def process_webhook_event(
        db: Session,
        raw_body: bytes,
        signature: str,
        event_id: str,
        provider_override: Optional[PaymentProvider] = None
    ) -> Tuple[bool, str, Optional[WebhookEvent]]:
        provider = provider_override or PaymentService.get_provider()
        payload_hash = hashlib.sha256(raw_body).hexdigest()

        # 1. Deduplication: Check if event_id already received
        existing_event = db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
        if existing_event and existing_event.processing_status == "PROCESSED":
            return True, "Duplicate webhook event already processed.", existing_event

        # 2. Raw Body HMAC-SHA256 Signature Verification
        secret = settings.RAZORPAY_WEBHOOK_SECRET or "test_webhook_secret_123"
        is_valid_sig = provider.verify_webhook_signature(raw_body, signature, secret)
        if not is_valid_sig:
            # Record failed event for audit
            failed_ev = WebhookEvent(
                event_id=event_id,
                event_type="unknown",
                payload_hash=payload_hash,
                payload={},
                processing_status="FAILED",
                error_code="INVALID_SIGNATURE",
                error_message="HMAC signature verification failed over raw request body."
            )
            db.add(failed_ev)
            try:
                db.commit()
            except Exception:
                db.rollback()
            return False, "Invalid webhook signature.", failed_ev

        # 3. Parse JSON payload
        try:
            payload: Dict[str, Any] = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            return False, f"Malformed JSON in webhook body: {str(e)}", None

        event_type = payload.get("event", "unknown")
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        webhook_ev = existing_event or WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            payload=payload,
            received_at=now,
            processing_status="RECEIVED"
        )
        if not existing_event:
            db.add(webhook_ev)
            db.commit()
            db.refresh(webhook_ev)

        # 4. Extract Entity and Locate PaymentTransaction
        payload_data = payload.get("payload", {})
        payment_entity = payload_data.get("payment", {}).get("entity", {})
        order_entity = payload_data.get("order", {}).get("entity", {})

        razorpay_order_id = payment_entity.get("order_id") or order_entity.get("id")
        razorpay_payment_id = payment_entity.get("id")

        tx: Optional[PaymentTransaction] = None
        if razorpay_order_id:
            tx = db.query(PaymentTransaction).filter(PaymentTransaction.razorpay_order_id == razorpay_order_id).first()
        if not tx and razorpay_payment_id:
            tx = db.query(PaymentTransaction).filter(PaymentTransaction.razorpay_payment_id == razorpay_payment_id).first()

        if not tx:
            webhook_ev.processing_status = "IGNORED"
            webhook_ev.error_message = f"No matching PaymentTransaction found for order '{razorpay_order_id}' or payment '{razorpay_payment_id}'."
            db.commit()
            return True, "Webhook received but no matching transaction found.", webhook_ev

        # 5. Apply Deterministic State Machine Transitions
        if razorpay_payment_id:
            tx.razorpay_payment_id = razorpay_payment_id

        if event_type in ("payment.captured", "order.paid"):
            # Never downgrade terminal states
            if tx.status != PaymentState.CAPTURED:
                PaymentStateMachine.transition(tx, PaymentState.CAPTURED, db=db)
                intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == tx.purchase_intent_id).first()
                if intent:
                    intent.status = "COMPLETED"

        elif event_type == "payment.failed":
            # Out-of-order protection: never downgrade a CAPTURED transaction
            if tx.status != PaymentState.CAPTURED:
                PaymentStateMachine.transition(
                    tx,
                    PaymentState.FAILED,
                    reason=payment_entity.get("error_description") or "Payment failed at gateway.",
                    error_code=payment_entity.get("error_code") or "GATEWAY_PAYMENT_FAILED",
                    db=db
                )

        elif event_type == "payment.authorized":
            if tx.status in (PaymentState.ORDER_CREATED, PaymentState.PAYMENT_PENDING):
                PaymentStateMachine.transition(tx, PaymentState.AUTHORIZED, db=db)

        # 6. Record PaymentAttempt audit for webhook capture
        provider_name = "razorpay" if isinstance(provider, RazorpayProvider) else "mock"
        prior_attempts = db.query(PaymentAttempt).filter(PaymentAttempt.payment_transaction_id == tx.id).count()
        attempt = PaymentAttempt(
            merchant_id=tx.merchant_id,
            payment_transaction_id=tx.id,
            attempt_number=prior_attempts + 1,
            provider=provider_name,
            operation="WEBHOOK_CAPTURE",
            idempotency_key=f"wh_{event_id}",
            request_fingerprint=payload_hash,
            status="SUCCESS" if tx.status == PaymentState.CAPTURED else "PROCESSED",
            provider_order_id=razorpay_order_id,
            provider_payment_id=razorpay_payment_id,
            trace_id=f"evt_{event_id}",
            started_at=now,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(attempt)

        webhook_ev.merchant_id = tx.merchant_id
        webhook_ev.processing_status = "PROCESSED"
        webhook_ev.processed_at = now

        db.flush()

        from app.services.audit_service import AuditService
        intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == tx.purchase_intent_id).first()
        assigned_trace = intent.trace_id if intent else f"evt_{event_id}"

        AuditService.record_event(
            db=db,
            merchant_id=tx.merchant_id,
            trace_id=assigned_trace,
            session_id=intent.session_id if intent else None,
            purchase_intent_id=tx.purchase_intent_id,
            authorization_id=tx.authorization_id,
            payment_transaction_id=tx.id,
            payment_attempt_id=attempt.id,
            webhook_event_id=webhook_ev.id,
            actor_type="WEBHOOK",
            action="PROCESS_WEBHOOK",
            event_type="WEBHOOK_RECEIVED",
            new_state=tx.status,
            status="SUCCESS" if tx.status == PaymentState.CAPTURED else "PROCESSED",
            metadata_json={
                "event_type": event_type,
                "event_id": event_id,
                "provider_payment_id": razorpay_payment_id,
                "provider_order_id": razorpay_order_id,
                "signature_valid": True
            }
        )

        db.commit()
        db.refresh(tx)
        db.refresh(webhook_ev)
        return True, f"Event '{event_type}' processed successfully.", webhook_ev

    @staticmethod
    def verify_payment_signature(
        db: Session,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        merchant_id: Optional[str] = None,
        provider_override: Optional[PaymentProvider] = None
    ) -> PaymentTransaction:
        """
        Verifies customer checkout return signature from Razorpay.
        Updates transaction to CAPTURED only after cryptographic HMAC-SHA256 signature verification.
        """
        query = db.query(PaymentTransaction).filter(PaymentTransaction.razorpay_order_id == razorpay_order_id)
        if merchant_id:
            query = query.filter(PaymentTransaction.merchant_id == merchant_id)
        tx = query.first()

        if not tx:
            raise HTTPException(
                status_code=404,
                detail=f"Payment transaction for order '{razorpay_order_id}' not found."
            )

        # Idempotency check: if already captured with this payment_id, return immediately
        if tx.status == PaymentState.CAPTURED and tx.razorpay_payment_id == razorpay_payment_id:
            return tx

        provider = provider_override or PaymentService.get_provider()
        is_valid = provider.verify_payment_signature(
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature
        )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        prior_attempts = db.query(PaymentAttempt).filter(PaymentAttempt.payment_transaction_id == tx.id).count()
        provider_name = "razorpay" if isinstance(provider, RazorpayProvider) else "mock"

        attempt = PaymentAttempt(
            merchant_id=tx.merchant_id,
            payment_transaction_id=tx.id,
            attempt_number=prior_attempts + 1,
            provider=provider_name,
            operation="VERIFY_SIGNATURE",
            idempotency_key=f"verify_{razorpay_payment_id[:16]}",
            request_fingerprint=hashlib.sha256(f"{razorpay_order_id}|{razorpay_payment_id}|{razorpay_signature}".encode("utf-8")).hexdigest(),
            status="SUCCESS" if is_valid else "FAILED",
            provider_order_id=razorpay_order_id,
            provider_payment_id=razorpay_payment_id,
            trace_id=f"trc_verify_{razorpay_payment_id[:8]}",
            started_at=now,
            completed_at=now
        )
        db.add(attempt)

        if not is_valid:
            db.commit()
            raise HTTPException(
                status_code=400,
                detail="Payment signature verification failed. The payment response was not authentic."
            )

        # Transition state to CAPTURED
        tx.razorpay_payment_id = razorpay_payment_id
        PaymentStateMachine.transition(tx, PaymentState.CAPTURED, db=db)

        # Mark Purchase Intent as COMPLETED
        intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == tx.purchase_intent_id).first()
        if intent:
            intent.status = "COMPLETED"

        # Mark NegotiatedOffer as ORDER_CONFIRMED if linked
        from app.database.models.negotiated_offer import NegotiatedOffer
        offer = db.query(NegotiatedOffer).filter(
            (NegotiatedOffer.payment_order_id == razorpay_order_id) |
            (NegotiatedOffer.negotiation_id == tx.purchase_intent_id) |
            (NegotiatedOffer.id == tx.purchase_intent_id)
        ).first()
        if offer:
            offer.status = "ORDER_CONFIRMED"
            if not offer.order_id:
                offer.order_id = f"ord_{offer.negotiation_id[:12]}"

        # Apply post-payment rewards, coins redemption, and voucher consumption idempotently
        if intent and intent.product_summary and isinstance(intent.product_summary, dict):
            pricing_data = intent.product_summary.get("pricing", {})
            user_record = db.query(User).filter((User.email == intent.buyer_id) | (User.id == intent.buyer_id)).first()
            if user_record and pricing_data:
                from app.services.reward_service import RewardService
                RewardService.apply_post_payment_rewards(
                    db=db,
                    merchant_id=tx.merchant_id,
                    user_id=user_record.id,
                    order_reference=intent.id[:8].upper(),
                    payment_transaction_id=tx.id,
                    pricing_data=pricing_data
                )

        # Record Audit Event
        from app.services.audit_service import AuditService
        assigned_trace = intent.trace_id if intent else f"trc_verify_{razorpay_payment_id[:8]}"
        AuditService.record_event(
            db=db,
            merchant_id=tx.merchant_id,
            trace_id=assigned_trace,
            session_id=intent.session_id if intent else None,
            purchase_intent_id=tx.purchase_intent_id,
            authorization_id=tx.authorization_id,
            payment_transaction_id=tx.id,
            payment_attempt_id=attempt.id,
            actor_type="USER",
            action="VERIFY_PAYMENT_SIGNATURE",
            event_type="PAYMENT_CAPTURED",
            previous_state=PaymentState.ORDER_CREATED,
            new_state=PaymentState.CAPTURED,
            status="SUCCESS",
            metadata_json={
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "signature_valid": True,
                "amount": str(tx.amount),
                "currency": tx.currency
            }
        )

        db.commit()
        db.refresh(tx)
        return tx
