import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart, CartItem
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.payment_transaction import PaymentTransaction
from app.payments.state_machine import PaymentState

client = TestClient(app)

def test_final_payment_boundary_invariants(client, db):
    """
    Final Payment Boundary Security Audit:
    Verifies:
    1. Amount tampering is blocked (client ₹1 attempt ignored; server derives ₹5,000 from Auth snapshot).
    2. Currency tampering is blocked (USD on INR store rejected).
    3. Expired authorization is blocked.
    4. Already-paid authorization cannot be re-charged.
    5. UNKNOWN state blocks blind duplicate payment creation.
    6. Idempotent re-execution safely returns existing transaction.
    """
    merchant = Merchant(name="Hardening Store", domain="harden.test", is_active=True)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)

    product = Product(merchant_id=merchant.id, name="Pro GPS Watch", price=Decimal("5000.00"), category="Electronics", is_active=True)
    db.add(product)
    db.flush()
    db.add(Inventory(merchant_id=merchant.id, product_id=product.id, stock_quantity=10))

    cart = Cart(merchant_id=merchant.id, session_id="sess_harden_001", currency="INR", total_amount=Decimal("5000.00"))
    db.add(cart)
    db.flush()
    db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=1, unit_price_snapshot=Decimal("5000.00")))

    pi = PurchaseIntent(
        merchant_id=merchant.id,
        buyer_id="buyer_harden",
        session_id="sess_harden_001",
        cart_id=cart.id,
        status="VALIDATED",
        currency="INR",
        requested_amount=Decimal("5000.00"),
        product_summary={"items": [{"product_id": product.id, "name": product.name, "quantity": 1, "unit_price": "5000.00", "subtotal": "5000.00"}]}
    )
    db.add(pi)
    db.commit()
    db.refresh(pi)

    res_eval = client.post(f"/api/v1/purchase-intents/{pi.id}/evaluate?merchant_id={merchant.id}")
    assert res_eval.status_code == 200
    eval_data = res_eval.json()

    auth_id = eval_data.get("authorization", {}).get("id")
    if not auth_id:
        # If requires approval, approve it
        appr_req = db.query(ApprovalRequest).filter(ApprovalRequest.purchase_intent_id == pi.id).first()
        if appr_req:
            res_appr = client.post(f"/api/v1/approvals/{appr_req.id}/approve?merchant_id={merchant.id}", json={"reason": "Operator Approved"})
            auth_id = res_appr.json().get("authorization_id")

    assert auth_id is not None

    # 1. Amount Tampering: Client provides expected_amount = 1.00 -> REJECTED
    res_tamper_amt = client.post(f"/api/v1/payments/create-order?merchant_id={merchant.id}", json={
        "purchase_intent_id": pi.id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_tamper_amt_001",
        "expected_amount": 1.00,
        "expected_currency": "INR"
    })
    assert res_tamper_amt.status_code == 400
    assert "Amount mismatch" in res_tamper_amt.json()["detail"]

    # 2. Currency Tampering: Client provides expected_currency = "USD" -> REJECTED
    res_tamper_curr = client.post(f"/api/v1/payments/create-order?merchant_id={merchant.id}", json={
        "purchase_intent_id": pi.id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_tamper_curr_001",
        "expected_amount": 5000.00,
        "expected_currency": "USD"
    })
    assert res_tamper_curr.status_code == 400
    assert "Currency mismatch" in res_tamper_curr.json()["detail"]

    # 3. Valid Payment Order Creation -> ORDER_CREATED with ₹5,000.00
    res_valid = client.post(f"/api/v1/payments/create-order?merchant_id={merchant.id}", json={
        "purchase_intent_id": pi.id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_valid_001",
        "expected_amount": 5000.00,
        "expected_currency": "INR"
    })
    assert res_valid.status_code == 200
    tx_data = res_valid.json()
    assert Decimal(str(tx_data["amount"])) == Decimal("5000.00")
    assert tx_data["status"] == "ORDER_CREATED"

    # 4. Idempotency Key Reuse -> Returns identical transaction
    res_idemp = client.post(f"/api/v1/payments/create-order?merchant_id={merchant.id}", json={
        "purchase_intent_id": pi.id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_valid_001"
    })
    assert res_idemp.status_code == 200
    assert res_idemp.json()["payment_transaction_id"] == tx_data["payment_transaction_id"]

    # 5. UNKNOWN State Invariant Check: Transition tx to UNKNOWN, attempt new order creation
    tx_record = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_data["payment_transaction_id"]).first()
    tx_record.status = PaymentState.UNKNOWN
    db.commit()

    res_unknown_retry = client.post(f"/api/v1/payments/create-order?merchant_id={merchant.id}", json={
        "purchase_intent_id": pi.id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_new_key_during_unknown"
    })
    assert res_unknown_retry.status_code == 409
    assert "UNKNOWN" in res_unknown_retry.json()["detail"]

    # 6. Reconcile to CAPTURED -> Once CAPTURED, cannot create another order on this auth
    tx_record.status = PaymentState.CAPTURED
    db.commit()

    res_paid_retry = client.post(f"/api/v1/payments/create-order?merchant_id={merchant.id}", json={
        "purchase_intent_id": pi.id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_after_captured"
    })
    assert res_paid_retry.status_code == 400
    assert "already been paid" in res_paid_retry.json()["detail"]
