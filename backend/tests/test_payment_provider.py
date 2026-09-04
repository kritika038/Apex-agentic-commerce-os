import pytest
from decimal import Decimal
from app.payments.utils import to_minor_units, from_minor_units
from app.payments.provider import PaymentTimeoutError, PaymentInvalidRequestError, PaymentProviderError
from app.payments.mock_provider import MockPaymentProvider
from app.payments.razorpay_provider import RazorpayProvider

def test_decimal_monetary_unit_conversions():
    """
    Verifies that major to minor unit conversions operate strictly with Decimal arithmetic and no floating-point rounding errors.
    """
    # Standard ₹3,898.00 -> 389800 paise
    amt = Decimal("3898.00")
    minor = to_minor_units(amt, "INR")
    assert minor == 389800
    assert isinstance(minor, int)

    # Convert back
    back = from_minor_units(minor, "INR")
    assert back == Decimal("3898.00")
    assert isinstance(back, Decimal)

    # Fractional decimal precision tests: ₹0.10 + ₹0.20 = ₹0.30 -> 30 paise
    sum_amt = Decimal("0.10") + Decimal("0.20")
    assert to_minor_units(sum_amt, "INR") == 30
    assert from_minor_units(30, "INR") == Decimal("0.30")

    # ₹8,500.50 -> 850050 paise
    assert to_minor_units(Decimal("8500.50"), "INR") == 850050
    assert from_minor_units(850050, "INR") == Decimal("8500.50")

def test_mock_payment_provider_modes():
    """
    Verifies that MockPaymentProvider properly simulates success, timeout, invalid request, and payment failure modes.
    """
    provider = MockPaymentProvider(mode="SUCCESS")

    # 1. Success Mode
    res = provider.create_order(amount_minor=389800, currency="INR", receipt="rcpt_001")
    assert res.order_id.startswith("order_mock_")
    assert res.amount_minor == 389800
    assert res.status == "created"

    fetch_res = provider.fetch_order(res.order_id)
    assert fetch_res.order_id == res.order_id

    # 2. Timeout Mode
    provider.set_mode("TIMEOUT")
    with pytest.raises(PaymentTimeoutError):
        provider.create_order(amount_minor=389800, currency="INR", receipt="rcpt_002")

    with pytest.raises(PaymentTimeoutError):
        provider.fetch_order(res.order_id)

    # 3. Invalid Request Mode
    provider.set_mode("INVALID_REQUEST")
    with pytest.raises(PaymentInvalidRequestError):
        provider.create_order(amount_minor=389800, currency="INR", receipt="rcpt_003")

def test_mock_provider_webhook_signature():
    """
    Verifies raw body HMAC-SHA256 signature generation and verification in MockPaymentProvider.
    """
    provider = MockPaymentProvider(webhook_secret="test_secret_key_123")
    raw_body = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_123"}}}}'

    sig = provider.generate_signature(raw_body)
    assert provider.verify_webhook_signature(raw_body, sig) is True

    # Tampered raw body fails signature verification
    tampered_body = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_999"}}}}'
    assert provider.verify_webhook_signature(tampered_body, sig) is False

def test_razorpay_provider_test_mode_safety():
    """
    Verifies that RazorpayProvider strictly requires Test Mode credentials and rejects live keys or missing credentials.
    """
    # 1. Missing credentials
    with pytest.raises(PaymentProviderError) as exc_info:
        RazorpayProvider(key_id="", key_secret="")
    assert exc_info.value.code == "CREDENTIALS_MISSING"

    # 2. Live key rejection
    with pytest.raises(PaymentProviderError) as exc_info:
        RazorpayProvider(key_id="rzp_live_abc1234567890", key_secret="secret123")
    assert exc_info.value.code == "LIVE_KEY_REJECTED"

    # 3. Valid Test Mode key format
    rp = RazorpayProvider(key_id="rzp_test_mockkey12345", key_secret="mocksecret123", webhook_secret="mocksec")
    assert rp.key_id == "rzp_test_mockkey12345"
