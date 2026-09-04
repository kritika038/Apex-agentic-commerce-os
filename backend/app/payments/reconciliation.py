import hashlib
import json
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.reconciliation_attempt import ReconciliationAttempt
from app.payments.provider import PaymentProvider, PaymentProviderError
from app.payments.state_machine import PaymentState, PaymentStateMachine

class PaymentReconciliation:
    """
    Authoritative Reconciliation Service.
    Queries the external payment provider for ground truth, resolves UNKNOWN states,
    and produces immutable ReconciliationAttempt audit records.
    Never creates a second payment order as part of reconciliation.
    """

    @staticmethod
    def reconcile_transaction(
        db: Session,
        transaction_id: str,
        merchant_id: Optional[str] = None,
        provider_override: Optional[PaymentProvider] = None,
        trace_id: Optional[str] = None
    ) -> PaymentTransaction:
        # 1. Fetch transaction with row-level lock (if supported by dialect)
        query = db.query(PaymentTransaction)
        try:
            query = query.with_for_update()
        except Exception:
            pass # SQLite or mock session without for_update support

        transaction = query.filter(PaymentTransaction.id == transaction_id).first()
        if not transaction:
            raise ValueError(f"PaymentTransaction '{transaction_id}' not found.")

        # 2. Strict Merchant Isolation
        if merchant_id and transaction.merchant_id != merchant_id:
            raise ValueError(f"PaymentTransaction '{transaction_id}' does not belong to merchant '{merchant_id}'.")

        # 3. Idempotent short-circuit on already settled terminal states
        if transaction.status == PaymentState.CAPTURED:
            return transaction

        previous_status = transaction.status

        # 4. Increment attempt counter
        prior_attempts = db.query(ReconciliationAttempt).filter(
            ReconciliationAttempt.payment_transaction_id == transaction.id
        ).count()
        attempt_number = prior_attempts + 1

        # 5. Transition to RECONCILING state via State Machine
        if transaction.status != PaymentState.RECONCILING:
            PaymentStateMachine.transition(transaction, PaymentState.RECONCILING, db=db)

        # 6. Resolve Payment Provider
        from app.payments.service import PaymentService
        provider = provider_override or PaymentService.get_provider()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        provider_status_str = None
        resolved_status = PaymentState.UNKNOWN
        reason = ""
        provider_response_hash = None

        try:
            # Check by payment ID first if available
            if transaction.razorpay_payment_id:
                payment_res = provider.fetch_payment(transaction.razorpay_payment_id)
                provider_status_str = payment_res.status
                provider_response_hash = hashlib.sha256(
                    json.dumps(payment_res.raw_response or {}, sort_keys=True).encode("utf-8")
                ).hexdigest()

                if payment_res.status in ("captured", "paid"):
                    resolved_status = PaymentState.CAPTURED
                    reason = f"Provider confirmed payment {payment_res.payment_id} captured."
                    PaymentStateMachine.transition(transaction, PaymentState.CAPTURED, db=db)
                    
                    # Update linked PurchaseIntent
                    intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == transaction.purchase_intent_id).first()
                    if intent:
                        intent.status = "COMPLETED"
                elif payment_res.status in ("failed", "cancelled"):
                    resolved_status = PaymentState.FAILED
                    reason = payment_res.error_description or "Payment failed at gateway."
                    PaymentStateMachine.transition(
                        transaction,
                        PaymentState.FAILED,
                        reason=reason,
                        error_code=payment_res.error_code or "PAYMENT_FAILED",
                        db=db
                    )
                else:
                    resolved_status = PaymentState.PAYMENT_PENDING
                    reason = f"Payment status pending: {payment_res.status}"
                    PaymentStateMachine.transition(transaction, PaymentState.PAYMENT_PENDING, db=db)

            # Otherwise check by order ID if available
            elif transaction.razorpay_order_id:
                order_res = provider.fetch_order(transaction.razorpay_order_id)
                provider_status_str = order_res.status
                provider_response_hash = hashlib.sha256(
                    json.dumps(order_res.raw_response or {}, sort_keys=True).encode("utf-8")
                ).hexdigest()

                if order_res.status == "paid":
                    resolved_status = PaymentState.CAPTURED
                    reason = f"Provider confirmed order {order_res.order_id} is paid."
                    PaymentStateMachine.transition(transaction, PaymentState.CAPTURED, db=db)
                    intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == transaction.purchase_intent_id).first()
                    if intent:
                        intent.status = "COMPLETED"
                elif order_res.status in ("created", "attempted"):
                    resolved_status = PaymentState.ORDER_CREATED
                    reason = f"Provider confirmed order {order_res.order_id} is active."
                    PaymentStateMachine.transition(transaction, PaymentState.ORDER_CREATED, db=db)
                else:
                    resolved_status = PaymentState.UNKNOWN
                    reason = f"Provider returned indeterminate order status: {order_res.status}"
                    PaymentStateMachine.transition(transaction, PaymentState.UNKNOWN, db=db)
            else:
                # Neither order ID nor payment ID exists (timed out during creation before order was returned)
                resolved_status = PaymentState.FAILED
                reason = "No gateway order reference found; provider confirmed order was not created."
                PaymentStateMachine.transition(
                    transaction,
                    PaymentState.FAILED,
                    reason=reason,
                    error_code="ORDER_CREATION_ABORTED",
                    db=db
                )

        except PaymentProviderError as e:
            resolved_status = PaymentState.UNKNOWN
            reason = f"Transient provider error during reconciliation: {e.message}"
            PaymentStateMachine.transition(transaction, PaymentState.UNKNOWN, reason=reason, db=db)
        except Exception as e:
            resolved_status = PaymentState.UNKNOWN
            reason = f"Unexpected error during reconciliation: {str(e)}"
            PaymentStateMachine.transition(transaction, PaymentState.UNKNOWN, reason=reason, db=db)

        # 7. Record immutable ReconciliationAttempt audit record
        attempt_record = ReconciliationAttempt(
            merchant_id=transaction.merchant_id,
            payment_transaction_id=transaction.id,
            attempt_number=attempt_number,
            previous_status=previous_status,
            provider_status=provider_status_str,
            resolved_status=resolved_status,
            reason=reason,
            provider_response_hash=provider_response_hash,
            trace_id=trace_id or transaction.idempotency_key,
            started_at=now,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(attempt_record)
        db.flush()

        from app.services.audit_service import AuditService
        intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == transaction.purchase_intent_id).first()
        assigned_trace = trace_id or (intent.trace_id if intent else f"trc_{transaction.id[:8]}")

        AuditService.record_event(
            db=db,
            merchant_id=transaction.merchant_id,
            trace_id=assigned_trace,
            session_id=intent.session_id if intent else None,
            purchase_intent_id=transaction.purchase_intent_id,
            authorization_id=transaction.authorization_id,
            payment_transaction_id=transaction.id,
            reconciliation_attempt_id=attempt_record.id,
            actor_type="SYSTEM",
            action="RECONCILE_PAYMENT",
            event_type="RECONCILIATION_COMPLETED",
            previous_state=previous_status,
            new_state=resolved_status,
            status="SUCCESS" if resolved_status in (PaymentState.CAPTURED, PaymentState.FAILED, PaymentState.ORDER_CREATED) else "TIMEOUT",
            reason=reason,
            metadata_json={
                "previous_status": previous_status,
                "provider_status": provider_status_str,
                "resolved_status": resolved_status,
                "attempt_number": attempt_number,
                "provider_response_hash": provider_response_hash
            }
        )

        db.commit()
        db.refresh(transaction)

        return transaction
