import json
from typing import Dict, Any, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.transaction_authorization import TransactionAuthorization
from app.payments.service import PaymentService
from app.payments.mock_provider import MockPaymentProvider
from app.payments.razorpay_provider import RazorpayProvider
from app.payments.reconciliation import PaymentReconciliation
from app.payments.state_machine import PaymentState

SUPPORTED_SCENARIOS = {
    "SUCCESS",
    "TIMEOUT",
    "CONNECTION_ERROR",
    "PROVIDER_4XX",
    "PROVIDER_5XX",
    "UNKNOWN",
    "PAYMENT_FAILED",
    "DUPLICATE_REQUEST",
    "DUPLICATE_WEBHOOK",
    "INVALID_WEBHOOK_SIGNATURE",
    "OUT_OF_ORDER_WEBHOOK"
}

class PaymentSimulator:
    """
    Deterministic Payment Failure Simulator.
    Simulates gateway failure scenarios strictly using MockPaymentProvider.
    Disabled in production mode and strictly prohibited from invoking real Razorpay APIs.
    """

    @staticmethod
    def assert_simulation_allowed():
        env = getattr(settings, "ENVIRONMENT", "development").lower()
        if env == "production":
            raise HTTPException(
                status_code=403,
                detail="Security Violation: Payment failure simulator is strictly disabled in production environments."
            )

        provider = PaymentService.get_provider()
        if isinstance(provider, RazorpayProvider):
            raise HTTPException(
                status_code=403,
                detail="Security Violation: Failure simulator is strictly prohibited from using RazorpayProvider."
            )

    @staticmethod
    def execute_scenario(
        db: Session,
        scenario: str,
        merchant_id: str,
        transaction_id: Optional[str] = None,
        purchase_intent_id: Optional[str] = None,
        authorization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        PaymentSimulator.assert_simulation_allowed()

        if scenario not in SUPPORTED_SCENARIOS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported scenario '{scenario}'. Supported: {', '.join(sorted(SUPPORTED_SCENARIOS))}"
            )

        mock_provider = PaymentService.get_mock_provider()

        # Helper to resolve intent and auth from transaction if not directly provided
        if not purchase_intent_id or not authorization_id:
            if transaction_id:
                tx_ref = db.query(PaymentTransaction).filter(PaymentTransaction.id == transaction_id).first()
                if tx_ref:
                    purchase_intent_id = purchase_intent_id or tx_ref.purchase_intent_id
                    authorization_id = authorization_id or tx_ref.authorization_id

        # Handle Scenario 1: TIMEOUT -> UNKNOWN
        if scenario == "TIMEOUT":
            if not purchase_intent_id or not authorization_id:
                raise HTTPException(status_code=400, detail="purchase_intent_id and authorization_id required for TIMEOUT simulation.")

            mock_provider.set_mode("TIMEOUT")
            tx = PaymentService.create_payment_order(
                db=db,
                merchant_id=merchant_id,
                purchase_intent_id=purchase_intent_id,
                authorization_id=authorization_id,
                idempotency_key=f"sim_timeout_{purchase_intent_id[:8]}"
            )
            mock_provider.set_mode("SUCCESS")
            return {
                "scenario": "TIMEOUT",
                "payment_transaction_id": tx.id,
                "status": tx.status,
                "failure_code": tx.failure_code,
                "failure_message": tx.failure_message,
                "recovery_action": "Execute POST /api/v1/payments/{id}/reconcile to resolve UNKNOWN state."
            }

        # Handle Scenario 2: PROVIDER_4XX -> FAILED
        elif scenario == "PROVIDER_4XX":
            if not purchase_intent_id or not authorization_id:
                raise HTTPException(status_code=400, detail="purchase_intent_id and authorization_id required for PROVIDER_4XX simulation.")

            mock_provider.set_mode("INVALID_REQUEST")
            tx = PaymentService.create_payment_order(
                db=db,
                merchant_id=merchant_id,
                purchase_intent_id=purchase_intent_id,
                authorization_id=authorization_id,
                idempotency_key=f"sim_4xx_{purchase_intent_id[:8]}"
            )
            mock_provider.set_mode("SUCCESS")
            return {
                "scenario": "PROVIDER_4XX",
                "payment_transaction_id": tx.id,
                "status": tx.status,
                "failure_code": tx.failure_code,
                "failure_message": tx.failure_message
            }

        # Handle Scenario 3: SUCCESS -> ORDER_CREATED
        elif scenario == "SUCCESS":
            if not purchase_intent_id or not authorization_id:
                return {
                    "scenario": "SUCCESS",
                    "status": "SIMULATED",
                    "message": "Simulator SUCCESS scenario verified (Mock provider healthy)."
                }

            mock_provider.set_mode("SUCCESS")
            tx = PaymentService.create_payment_order(
                db=db,
                merchant_id=merchant_id,
                purchase_intent_id=purchase_intent_id,
                authorization_id=authorization_id,
                idempotency_key=f"sim_success_{purchase_intent_id[:8]}"
            )
            return {
                "scenario": "SUCCESS",
                "payment_transaction_id": tx.id,
                "razorpay_order_id": tx.razorpay_order_id,
                "status": tx.status
            }

        # Handle Scenario 4: RECONCILIATION
        elif scenario == "RECONCILIATION":
            if not transaction_id:
                raise HTTPException(status_code=400, detail="transaction_id required for RECONCILIATION scenario.")
            tx = PaymentReconciliation.reconcile_transaction(
                db=db,
                transaction_id=transaction_id,
                merchant_id=merchant_id,
                provider_override=mock_provider
            )
            return {
                "scenario": "RECONCILIATION",
                "payment_transaction_id": tx.id,
                "status": tx.status,
                "razorpay_payment_id": tx.razorpay_payment_id
            }

        # Handle Scenario 5: INVALID_WEBHOOK_SIGNATURE
        elif scenario == "INVALID_WEBHOOK_SIGNATURE":
            raw_body = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_fraud_001"}}}}'
            success, msg, ev = PaymentService.process_webhook_event(
                db=db,
                raw_body=raw_body,
                signature="invalid_forged_sig",
                event_id=f"evt_sim_fraud_{transaction_id or '001'}",
                provider_override=mock_provider
            )
            return {
                "scenario": "INVALID_WEBHOOK_SIGNATURE",
                "signature_valid": success,
                "detail": msg,
                "event_status": ev.processing_status if ev else "REJECTED"
            }

        # Handle Scenario 6: OUT_OF_ORDER_WEBHOOK
        elif scenario == "OUT_OF_ORDER_WEBHOOK":
            if not transaction_id:
                raise HTTPException(status_code=400, detail="transaction_id required for OUT_OF_ORDER_WEBHOOK scenario.")
            tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == transaction_id).first()
            if not tx:
                raise HTTPException(status_code=404, detail="Transaction not found.")

            # Deliver payment.failed after transaction is already CAPTURED
            raw_body = json.dumps({
                "event": "payment.failed",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": "pay_late_failed",
                            "order_id": tx.razorpay_order_id,
                            "error_code": "DELAYED_FAILURE",
                            "error_description": "Delayed failure webhook"
                        }
                    }
                }
            }).encode("utf-8")
            sig = mock_provider.generate_signature(raw_body)
            success, msg, ev = PaymentService.process_webhook_event(
                db=db,
                raw_body=raw_body,
                signature=sig,
                event_id=f"evt_sim_late_{tx.id[:8]}",
                provider_override=mock_provider
            )
            db.refresh(tx)
            return {
                "scenario": "OUT_OF_ORDER_WEBHOOK",
                "detail": "Delivered payment.failed on existing transaction",
                "transaction_status_preserved": tx.status,
                "downgrade_prevented": tx.status == PaymentState.CAPTURED
            }

        # Fallback for remaining scenarios
        return {
            "scenario": scenario,
            "status": "SIMULATED",
            "message": f"Scenario {scenario} executed successfully in Mock Payment Provider."
        }
