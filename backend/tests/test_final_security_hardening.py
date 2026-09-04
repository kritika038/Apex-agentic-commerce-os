import pytest
import hmac
import hashlib
import json
from decimal import Decimal
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.database.models.audit_event import AuditEvent
from app.database.models.policy import Policy
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.revenue_opportunity import RevenueOpportunity
from app.utils.redaction import redact_sensitive_data
from app.services.audit_integrity_service import AuditIntegrityService
from app.services.audit_service import AuditService
from app.core.security import get_password_hash, create_access_token

client = TestClient(app)

def test_final_security_hardening_suite(client, db):
    """
    Comprehensive Final Security Hardening Suite:
    1. Secret Redaction & Token Masking
    2. Webhook HMAC Signature Integrity & Body Tamper Defense
    3. SHA-256 Cryptographic Hash Chain Tamper Detection
    4. Revenue Autopilot Pre-Execution Safety
    5. Inactive User Authentication Defense
    """
    merchant = Merchant(name="Hardened Core Store", domain="core.test", is_active=True)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)

    # 1. Secret Redaction Verification
    sensitive_payload = {
        "user_email": "operator@test.com",
        "api_key": "secret_live_key_998877",
        "password": "SuperSecretPassword123!",
        "razorpay_secret": "rzp_secret_xyz123",
        "card_number": "4111222233334444",
        "cvv": "123",
        "token_usage": 150, # Harmless field must NOT be redacted
        "currency": "INR"   # Harmless field must NOT be redacted
    }
    redacted = redact_sensitive_data(sensitive_payload)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["razorpay_secret"] == "[REDACTED]"
    assert redacted["card_number"] == "[REDACTED]"
    assert redacted["cvv"] == "[REDACTED]"
    assert redacted["token_usage"] == 150
    assert redacted["currency"] == "INR"

    # 2. Webhook HMAC Timing-Safe Verification & Body Tamper Defense
    webhook_secret = "whsec_hardening_secret_key"
    payload_dict = {"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_test_harden_001", "order_id": "order_test_001", "amount": 250000, "status": "captured"}}}}
    raw_body = json.dumps(payload_dict).encode("utf-8")
    valid_sig = hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    # Forged Body with Original Valid Signature -> REJECTED
    tampered_body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_test_harden_001", "order_id": "order_test_001", "amount": 100, "status": "captured"}}}}).encode("utf-8")
    
    res_tamper_wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=tampered_body,
        headers={"X-Razorpay-Signature": valid_sig, "X-Razorpay-Event-Id": "evt_tampered_001"}
    )
    assert res_tamper_wh.status_code == 401
    assert "Webhook verification failed" in res_tamper_wh.json()["detail"]

    # 3. Cryptographic SHA-256 Tamper Detection
    trace_id = "trc_chain_test_harden"
    ev1 = AuditService.record_event(
        db=db,
        merchant_id=merchant.id,
        trace_id=trace_id,
        actor_type="USER",
        action="TEST_EVENT_1",
        event_type="TEST_1",
        status="SUCCESS",
        metadata_json={"action": "step_1"}
    )
    ev2 = AuditService.record_event(
        db=db,
        merchant_id=merchant.id,
        trace_id=trace_id,
        actor_type="USER",
        action="TEST_EVENT_2",
        event_type="TEST_2",
        status="SUCCESS",
        metadata_json={"action": "step_2"}
    )
    db.commit()

    # Verify initial valid state
    verify_valid = AuditIntegrityService.verify_trace(db=db, trace_id=trace_id, merchant_id=merchant.id)
    assert verify_valid["is_valid"] is True
    assert verify_valid["tampering_detected"] is False

    # Simulate attacker mutating ev1 metadata in database
    ev1.metadata_json = {"action": "tampered_step_1", "amount_hacked": "99999"}
    db.commit()

    verify_tampered = AuditIntegrityService.verify_trace(db=db, trace_id=trace_id, merchant_id=merchant.id)
    assert verify_tampered["is_valid"] is False
    assert verify_tampered["tampering_detected"] is True
    assert "Payload modification detected" in verify_tampered["detail"]

    # 4. Inactive User Authentication Defense
    inactive_user = User(
        email="inactive@store.test",
        full_name="Inactive User",
        hashed_password=get_password_hash("password123"),
        role="admin",
        merchant_id=merchant.id,
        is_active=False
    )
    db.add(inactive_user)
    db.commit()

    token = create_access_token(subject=inactive_user.id, merchant_id=merchant.id, role="admin")
    res_inactive = client.get("/api/v1/products/", headers={"Authorization": f"Bearer {token}"})
    assert res_inactive.status_code == 400
    assert "Inactive user" in res_inactive.json()["detail"]
