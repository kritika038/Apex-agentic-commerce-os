import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.transaction_authorization import TransactionAuthorization
from app.services.audit_integrity_service import AuditIntegrityService

def _seed_sample_catalog(db: Session, merchant_id: str):
    p1 = db.query(Product).filter(Product.merchant_id == merchant_id, Product.name == "Pro Running Shoes").first()
    if not p1:
        p1 = Product(merchant_id=merchant_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
        db.add(p1)
        db.flush()
        db.add(Inventory(merchant_id=merchant_id, product_id=p1.id, stock_quantity=10))
        db.commit()
    return p1

def test_protocol_purchase_intent_authoritative_pricing(client: TestClient, db: Session, setup_test_data):
    """
    Security Test: Protocol purchase intent derives total strictly from database product prices.
    Client-supplied price attempts in constraints/payload have zero effect.
    """
    m1_id = setup_test_data["m1"]
    p1 = _seed_sample_catalog(db, m1_id)
    session_id = "sess_proto_sec_01"
    trace_id = "trc_proto_sec_01"

    # Add 2 items
    client.post("/api/v1/ai/shopping", json={
        "session_id": session_id,
        "merchant_id": m1_id,
        "message": f"add product {p1.id} to cart",
        "trace_id": trace_id
    })

    # Call protocol purchase intent with malicious constraint trying to force lower price
    res_pi = client.post(f"/api/v1/protocol/purchase-intent?merchant_id={m1_id}", json={
        "session_id": session_id,
        "buyer_id": "malicious_bot",
        "constraints": {"force_price": 10.0, "amount": 10.0},
        "trace_id": trace_id
    })
    assert res_pi.status_code == 200
    pi_data = res_pi.json()

    # Authoritative amount MUST be ₹3499.00
    assert Decimal(str(pi_data["requested_amount"])) == Decimal("3499.00")

def test_protocol_payment_request_requires_valid_authorization(client: TestClient, db: Session, setup_test_data):
    """
    Security Test: /api/v1/protocol/payment-request strictly fails if authorization is forged,
    expired, or non-existent.
    """
    m1_id = setup_test_data["m1"]
    p1 = _seed_sample_catalog(db, m1_id)
    session_id = "sess_proto_pay_sec_01"
    trace_id = "trc_proto_pay_sec_01"

    client.post("/api/v1/ai/shopping", json={
        "session_id": session_id,
        "merchant_id": m1_id,
        "message": f"add product {p1.id} to cart",
        "trace_id": trace_id
    })

    res_pi = client.post(f"/api/v1/protocol/purchase-intent?merchant_id={m1_id}", json={
        "session_id": session_id,
        "buyer_id": "buyer_test",
        "trace_id": trace_id
    })
    pi_id = res_pi.json()["purchase_intent_id"]

    # 1. Attempt payment with forged authorization ID -> 404 / 400
    res_forged = client.post(f"/api/v1/protocol/payment-request?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": "forged_auth_id_12345",
        "idempotency_key": "idemp_proto_forged_01",
        "trace_id": trace_id
    })
    assert res_forged.status_code in [400, 404]

    # 2. Check authorization lookup endpoint
    res_auth_lookup = client.get(f"/api/v1/protocol/authorization/{pi_id}?merchant_id={m1_id}")
    assert res_auth_lookup.status_code == 200
    assert res_auth_lookup.json()["status"] == "NOT_EVALUATED"

def test_protocol_full_lifecycle_integrity(client: TestClient, db: Session, setup_test_data):
    """
    Test: Full protocol flow maintains cryptographic SHA-256 hash-chain integrity.
    """
    m1_id = setup_test_data["m1"]
    p1 = _seed_sample_catalog(db, m1_id)
    session_id = "sess_proto_e2e_01"
    trace_id = "trc_proto_e2e_01"

    # 1. Discover
    client.post(f"/api/v1/protocol/discover?merchant_id={m1_id}", json={
        "query": "Running",
        "trace_id": trace_id
    })

    # 2. Add to cart
    client.post("/api/v1/ai/shopping", json={
        "session_id": session_id,
        "merchant_id": m1_id,
        "message": f"add product {p1.id} to cart",
        "trace_id": trace_id
    })

    # 3. Recommend
    client.post(f"/api/v1/protocol/recommend?merchant_id={m1_id}", json={
        "session_id": session_id,
        "trace_id": trace_id
    })

    # 4. Purchase Intent
    res_pi = client.post(f"/api/v1/protocol/purchase-intent?merchant_id={m1_id}", json={
        "session_id": session_id,
        "buyer_id": "buyer_proto_e2e",
        "trace_id": trace_id
    })
    pi_id = res_pi.json()["purchase_intent_id"]

    # 5. Evaluate policy
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}&trace_id={trace_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    # 6. Authorization status lookup
    res_auth_status = client.get(f"/api/v1/protocol/authorization/{pi_id}?merchant_id={m1_id}")
    assert res_auth_status.status_code == 200
    assert res_auth_status.json()["status"] == "AUTHORIZED"

    # 7. Payment Request
    res_pay = client.post(f"/api/v1/protocol/payment-request?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_proto_lifecycle_01",
        "trace_id": trace_id
    })
    assert res_pay.status_code == 200

    # 8. Verify Cryptographic Integrity
    integrity = AuditIntegrityService.verify_trace(db=db, trace_id=trace_id, merchant_id=m1_id)
    assert integrity["is_valid"] is True
    assert integrity["tampering_detected"] is False
    assert integrity["event_count"] >= 5
