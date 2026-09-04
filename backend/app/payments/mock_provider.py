import hmac
import hashlib
import uuid
from typing import Optional, Dict, Any
from app.payments.provider import (
    PaymentProvider,
    OrderResult,
    PaymentResult,
    PaymentTimeoutError,
    PaymentInvalidRequestError
)

class MockPaymentProvider(PaymentProvider):
    """
    Deterministic Mock Payment Gateway Provider.
    Simulates real gateway responses, network timeouts, invalid requests, and payment lifecycles.
    """

    def __init__(self, mode: str = "SUCCESS", webhook_secret: str = "test_webhook_secret_123"):
        self.mode = mode # SUCCESS, TIMEOUT, INVALID_REQUEST, PAYMENT_FAILED
        self.webhook_secret = webhook_secret
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.payments: Dict[str, Dict[str, Any]] = {}

    def set_mode(self, mode: str):
        self.mode = mode

    def create_order(
        self,
        amount_minor: int,
        currency: str,
        receipt: str,
        notes: Optional[Dict[str, str]] = None
    ) -> OrderResult:
        if self.mode == "TIMEOUT":
            raise PaymentTimeoutError("Mock provider simulated timeout during order creation")
        elif self.mode == "INVALID_REQUEST":
            raise PaymentInvalidRequestError("Mock provider simulated invalid parameter error")

        order_id = f"order_mock_{uuid.uuid4().hex[:12]}"
        order_data = {
            "id": order_id,
            "amount": amount_minor,
            "currency": currency.upper(),
            "receipt": receipt,
            "status": "created",
            "notes": notes or {}
        }
        self.orders[order_id] = order_data

        return OrderResult(
            order_id=order_id,
            amount_minor=amount_minor,
            currency=currency.upper(),
            receipt=receipt,
            status="created",
            raw_response=order_data
        )

    def fetch_order(self, order_id: str) -> OrderResult:
        if self.mode == "TIMEOUT":
            raise PaymentTimeoutError("Mock provider simulated timeout during fetch_order")

        order_data = self.orders.get(order_id)
        if not order_data:
            # If not in local store, return a synthesized created order
            order_data = {
                "id": order_id,
                "amount": 0,
                "currency": "INR",
                "receipt": "",
                "status": "created"
            }

        return OrderResult(
            order_id=order_id,
            amount_minor=order_data["amount"],
            currency=order_data["currency"],
            receipt=order_data.get("receipt", ""),
            status=order_data.get("status", "created"),
            raw_response=order_data
        )

    def fetch_payment(self, payment_id: str) -> PaymentResult:
        if self.mode == "TIMEOUT":
            raise PaymentTimeoutError("Mock provider simulated timeout during fetch_payment")

        payment_data = self.payments.get(payment_id)
        if not payment_data:
            status = "failed" if self.mode == "PAYMENT_FAILED" else "captured"
            payment_data = {
                "id": payment_id,
                "order_id": None,
                "amount": 0,
                "currency": "INR",
                "status": status
            }

        return PaymentResult(
            payment_id=payment_id,
            order_id=payment_data.get("order_id"),
            amount_minor=payment_data.get("amount", 0),
            currency=payment_data.get("currency", "INR"),
            status=payment_data.get("status", "captured"),
            method="upi",
            raw_response=payment_data
        )

    def simulate_payment_success(self, order_id: str, amount_minor: int, currency: str = "INR") -> PaymentResult:
        """Helper to simulate successful payment for an existing order."""
        payment_id = f"pay_mock_{uuid.uuid4().hex[:12]}"
        payment_data = {
            "id": payment_id,
            "order_id": order_id,
            "amount": amount_minor,
            "currency": currency.upper(),
            "status": "captured",
            "method": "upi"
        }
        self.payments[payment_id] = payment_data

        if order_id in self.orders:
            self.orders[order_id]["status"] = "paid"

        return PaymentResult(
            payment_id=payment_id,
            order_id=order_id,
            amount_minor=amount_minor,
            currency=currency.upper(),
            status="captured",
            method="upi",
            raw_response=payment_data
        )

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature: str,
        secret: Optional[str] = None
    ) -> bool:
        sec = secret or self.webhook_secret
        if not sec or not signature:
            return False

        try:
            expected_signature = hmac.new(
                sec.encode("utf-8"),
                raw_body,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
        except Exception:
            return False

    def generate_signature(self, raw_body: bytes, secret: Optional[str] = None) -> str:
        sec = secret or self.webhook_secret
        return hmac.new(sec.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> bool:
        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            return False
        # Allow HMAC signature over order|payment or test mock signature prefix
        if razorpay_signature.startswith("mock_sig_") or razorpay_signature.startswith("sig_"):
            return True
        sec = self.webhook_secret or "mock_secret"
        try:
            msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
            expected_signature = hmac.new(sec.encode("utf-8"), msg, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected_signature, razorpay_signature)
        except Exception:
            return False
