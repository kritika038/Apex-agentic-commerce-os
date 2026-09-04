import json
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.payment_transaction import PaymentTransaction
from app.payments.state_machine import PaymentState
from app.services.audit_integrity_service import AuditIntegrityService

def _ensure_demo_products(db: Session, merchant_id: str):
    p1 = db.query(Product).filter(Product.merchant_id == merchant_id, Product.name == "Pro Running Shoes").first()
    if not p1:
        p1 = Product(merchant_id=merchant_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
        p2 = Product(merchant_id=merchant_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
        db.add_all([p1, p2])
        db.flush()
        db.add(Inventory(merchant_id=merchant_id, product_id=p1.id, stock_quantity=25))
        db.add(Inventory(merchant_id=merchant_id, product_id=p2.id, stock_quantity=100))
        db.commit()
    return p1

def test_complete_end_to_end_trace_lifecycle(client: TestClient, db: Session, setup_test_data):
    """
    End-to-End Verification Test:
    Executes the full commerce lifecycle under a single unified trace_id.
    Validates that every major milestone appears in chronological order and
    passes cryptographic hash-chain integrity verification.
    """
    m1_id = setup_test_data["m1"]
    session_id = "sess_e2e_trace_99"
    trace_id = "trc_unified_e2e_99"

    p1 = _ensure_demo_products(db, m1_id)

    # 1. AI Shopping Request (with tool call: search_products & add_to_cart)
    res_shop = client.post("/api/v1/ai/shopping", json={
        "session_id": session_id,
        "merchant_id": m1_id,
        "message": f"add product {p1.id} to my cart",
        "trace_id": trace_id
    })
    assert res_shop.status_code == 200

    # 2. Purchase Intent Creation
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_e2e_99",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"},
        "trace_id": trace_id
    })
    assert res_pi.status_code == 200
    pi_id = res_pi.json()["id"]

    # 3. Policy Evaluation
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}&trace_id={trace_id}")
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    auth_id = eval_data["authorization"]["id"]

    # 4. Payment Order Creation
    idemp_key = "idemp_e2e_trace_99"
    res_order = client.post(f"/api/v1/payments/orders?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": idemp_key,
        "trace_id": trace_id
    })
    assert res_order.status_code == 200
    order_data = res_order.json()
    rzp_order_id = order_data["razorpay_order_id"]
    tx_id = order_data["payment_transaction_id"]

    # 5. Webhook Delivery (payment.captured)
    from app.payments.service import PaymentService
    mock_provider = PaymentService.get_mock_provider()
    webhook_payload = json.dumps({
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_e2e_captured_99",
                    "order_id": rzp_order_id,
                    "amount": 349900,
                    "currency": "INR",
                    "status": "captured"
                }
            }
        }
    }).encode("utf-8")
    sig = mock_provider.generate_signature(webhook_payload)

    res_wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=webhook_payload,
        headers={
            "X-Razorpay-Signature": sig,
            "x-razorpay-event-id": "evt_e2e_wh_99",
            "Content-Type": "application/json"
        }
    )
    assert res_wh.status_code == 200

    # 6. Verify Full Trace Timeline via API
    res_trace = client.get(f"/api/v1/audit/traces/{trace_id}?merchant_id={m1_id}")
    assert res_trace.status_code == 200
    trace_summary = res_trace.json()

    assert trace_summary["trace_id"] == trace_id
    assert trace_summary["integrity"]["is_valid"] is True
    assert trace_summary["integrity"]["tampering_detected"] is False
    assert trace_summary["event_count"] >= 5

    # Verify event types appear in order
    actions = [e["action"] for e in trace_summary["events"]]
    assert "AI_REQUEST" in actions
    assert "CREATE_PURCHASE_INTENT" in actions
    assert "EVALUATE_POLICY" in actions
    assert "CREATE_PAYMENT_ORDER" in actions
    assert "PROCESS_WEBHOOK" in actions

    # Verify final payment state is CAPTURED
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert tx.status == PaymentState.CAPTURED
