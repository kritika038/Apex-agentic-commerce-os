from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any

class PaymentProviderError(Exception):
    def __init__(self, message: str, code: str = "PROVIDER_ERROR", raw_error: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.raw_error = raw_error or {}

class PaymentTimeoutError(PaymentProviderError):
    def __init__(self, message: str = "Payment gateway request timed out"):
        super().__init__(message, code="TIMEOUT")

class PaymentInvalidRequestError(PaymentProviderError):
    def __init__(self, message: str, raw_error: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="INVALID_REQUEST", raw_error=raw_error)

@dataclass
class OrderResult:
    order_id: str
    amount_minor: int
    currency: str
    receipt: str
    status: str # created, attempted, paid
    raw_response: Dict[str, Any]

@dataclass
class PaymentResult:
    payment_id: str
    order_id: Optional[str]
    amount_minor: int
    currency: str
    status: str # authorized, captured, failed
    method: Optional[str] = None
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None

class PaymentProvider(ABC):
    """
    Abstract payment gateway provider.
    Business logic and PaymentService must depend on this interface, never directly on vendor SDKs.
    """

    @abstractmethod
    def create_order(
        self,
        amount_minor: int,
        currency: str,
        receipt: str,
        notes: Optional[Dict[str, str]] = None
    ) -> OrderResult:
        """Creates an order in the payment gateway."""
        pass

    @abstractmethod
    def fetch_order(self, order_id: str) -> OrderResult:
        """Fetches the current status of an order from the gateway."""
        pass

    @abstractmethod
    def fetch_payment(self, payment_id: str) -> PaymentResult:
        """Fetches the current status of a payment from the gateway."""
        pass

    @abstractmethod
    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """Verifies the authenticity of a raw webhook payload using HMAC-SHA256."""
        pass

    @abstractmethod
    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> bool:
        """Verifies the client checkout return signature using HMAC-SHA256."""
        pass
