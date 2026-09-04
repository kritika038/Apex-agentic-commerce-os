import hmac
import hashlib
from typing import Optional, Dict, Any
import razorpay
from app.payments.provider import (
    PaymentProvider,
    OrderResult,
    PaymentResult,
    PaymentProviderError,
    PaymentTimeoutError,
    PaymentInvalidRequestError
)

class RazorpayProvider(PaymentProvider):
    """
    Official Razorpay Test Mode Payment Gateway Provider.
    Encapsulates all Razorpay SDK interactions and enforces test-mode constraints.
    """

    def __init__(self, key_id: str, key_secret: str, webhook_secret: Optional[str] = None):
        if not key_id or not key_secret:
            raise PaymentProviderError(
                "Razorpay credentials missing. RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be configured.",
                code="CREDENTIALS_MISSING"
            )

        # Enforce Test Mode Key Prefix Safety
        if not key_id.startswith("rzp_test_"):
            raise PaymentProviderError(
                "Unsupported key format: Razorpay Test Mode requires a key starting with 'rzp_test_'. Live credentials are prohibited.",
                code="LIVE_KEY_REJECTED"
            )

        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret
        self.client = razorpay.Client(auth=(key_id, key_secret))

    def create_order(
        self,
        amount_minor: int,
        currency: str,
        receipt: str,
        notes: Optional[Dict[str, str]] = None
    ) -> OrderResult:
        try:
            payload = {
                "amount": amount_minor,
                "currency": currency.upper(),
                "receipt": receipt,
                "notes": notes or {}
            }
            res = self.client.order.create(data=payload)
            return OrderResult(
                order_id=res["id"],
                amount_minor=int(res["amount"]),
                currency=res["currency"],
                receipt=res.get("receipt", receipt),
                status=res.get("status", "created"),
                raw_response=res
            )
        except razorpay.errors.BadRequestError as e:
            raise PaymentInvalidRequestError(str(e), raw_error={"message": str(e)})
        except razorpay.errors.ServerError as e:
            raise PaymentTimeoutError(f"Razorpay server error / timeout: {str(e)}")
        except Exception as e:
            err_msg = str(e)
            if "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
                raise PaymentTimeoutError(f"Razorpay connection timed out: {err_msg}")
            raise PaymentProviderError(f"Razorpay order creation failed: {err_msg}")

    def fetch_order(self, order_id: str) -> OrderResult:
        try:
            res = self.client.order.fetch(order_id)
            return OrderResult(
                order_id=res["id"],
                amount_minor=int(res["amount"]),
                currency=res["currency"],
                receipt=res.get("receipt", ""),
                status=res.get("status", "unknown"),
                raw_response=res
            )
        except razorpay.errors.BadRequestError as e:
            raise PaymentInvalidRequestError(str(e))
        except Exception as e:
            err_msg = str(e)
            if "timeout" in err_msg.lower():
                raise PaymentTimeoutError(f"Razorpay timeout on fetch_order: {err_msg}")
            raise PaymentProviderError(f"Failed to fetch Razorpay order: {err_msg}")

    def fetch_payment(self, payment_id: str) -> PaymentResult:
        try:
            res = self.client.payment.fetch(payment_id)
            return PaymentResult(
                payment_id=res["id"],
                order_id=res.get("order_id"),
                amount_minor=int(res["amount"]),
                currency=res["currency"],
                status=res.get("status", "unknown"),
                method=res.get("method"),
                error_code=res.get("error_code"),
                error_description=res.get("error_description"),
                raw_response=res
            )
        except Exception as e:
            err_msg = str(e)
            if "timeout" in err_msg.lower():
                raise PaymentTimeoutError(f"Razorpay timeout on fetch_payment: {err_msg}")
            raise PaymentProviderError(f"Failed to fetch Razorpay payment: {err_msg}")

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature: str,
        secret: Optional[str] = None
    ) -> bool:
        """
        Verifies HMAC-SHA256 signature using RAW request body bytes and constant-time string comparison.
        """
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

    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> bool:
        """
        Verifies the client checkout return signature using HMAC-SHA256 over f"{order_id}|{payment_id}".
        """
        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            return False

        try:
            msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
            expected_signature = hmac.new(
                self.key_secret.encode("utf-8"),
                msg,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_signature, razorpay_signature)
        except Exception:
            return False
