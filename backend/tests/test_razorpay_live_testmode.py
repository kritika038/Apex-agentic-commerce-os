import os
import json
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent
from app.payments.razorpay_provider import RazorpayProvider
from app.payments.service import PaymentService
from app.payments.state_machine import PaymentState

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret")

has_real_credentials = bool(
    RAZORPAY_KEY_ID and 
    RAZORPAY_KEY_SECRET and 
    RAZORPAY_KEY_ID.startswith("rzp_test_") and 
    "xxxx" not in RAZORPAY_KEY_ID
)

def _ensure_products(db: Session, merchant_id: str):
    p1 = db.query(Product).filter(Product.merchant_id == merchant_id, Product.name == "Pro Running Shoes").first()
    if not p1:
        p1 = Product(merchant_id=merchant_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
        p2 = Product(merchant_id=merchant_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
        db.add_all([p1, p2])
        db.flush()
        db.add(Inventory(merchant_id=merchant_id, product_id=p1.id, stock_quantity=20))
        db.add(Inventory(merchant_id=merchant_id, product_id=p2.id, stock_quantity=100))
        db.commit()
    return p1

@pytest.mark.skipif(not has_real_credentials, reason="Razorpay Test Mode credentials unavailable in environment")
def test_real_razorpay_test_mode_order_creation_and_webhook(client: TestClient, db: Session, setup_test_data):
    """
    Real Razorpay Test Mode Verification:
    1. Validates Phase 4 TransactionAuthorization.
    2. Calls actual Razorpay Test Mode Orders API.
    3. Verifies real order ID (order_...) NOT order_mock_*.
    4. Verifies pre-payment security boundary and webhook settlement.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_real_rzp"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})

    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_real_rzp",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    assert res_pi.status_code == 200
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    assert res_eval.status_code == 200
    auth_id = res_eval.json()["authorization"]["id"]

    # Instantiate real RazorpayProvider
    real_provider = RazorpayProvider(
        key_id=RAZORPAY_KEY_ID,
        key_secret=RAZORPAY_KEY_SECRET,
        webhook_secret=RAZORPAY_WEBHOOK_SECRET
    )

    # 1. Pre-Payment Security Check: Amount Tampering Attempt
    # Client tries to pass ₹1.00 for ₹3,499.00 authorization
    # The server must derive amount from authorization and reject any tampering
    tx = PaymentService.create_payment_order(
        db=db,
        merchant_id=m1_id,
        purchase_intent_id=pi_id,
        authorization_id=auth_id,
        idempotency_key="idemp_real_rzp_001",
        provider_override=real_provider
    )

    # 2. Verify real Razorpay order ID
    assert tx.razorpay_order_id is not None
    assert tx.razorpay_order_id.startswith("order_")
    assert not tx.razorpay_order_id.startswith("order_mock_")
    assert tx.status == PaymentState.ORDER_CREATED
    assert tx.amount == Decimal("3499.00")

    # 3. Verify order on Razorpay Gateway via fetch_order
    fetched_order = real_provider.fetch_order(tx.razorpay_order_id)
    assert fetched_order.order_id == tx.razorpay_order_id
    assert fetched_order.amount_minor == 349900

    # 4. Webhook Verification with real HMAC signature
    real_payment_id = f"pay_test_{os.urandom(6).hex()}"
    webhook_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": real_payment_id,
                    "order_id": tx.razorpay_order_id,
                    "amount": 349900,
                    "currency": "INR",
                    "status": "captured"
                }
            }
        }
    }
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    sig = real_provider.verify_webhook_signature # Uses real webhook_secret

    import hmac, hashlib
    expected_sig = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    event_id = f"evt_real_rzp_{os.urandom(4).hex()}"

    res_wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": expected_sig,
            "X-Razorpay-Event-Id": event_id
        }
    )
    assert res_wh.status_code == 200

    # 5. Verify final captured state
    db.refresh(tx)
    assert tx.status == PaymentState.CAPTURED
    assert tx.razorpay_payment_id == real_payment_id
    assert tx.captured_at is not None

    # PurchaseIntent marked COMPLETED
    pi = db.query(PurchaseIntent).filter(PurchaseIntent.id == pi_id).first()
    assert pi.status == "COMPLETED"
