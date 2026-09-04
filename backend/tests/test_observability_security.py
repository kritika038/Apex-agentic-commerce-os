import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.utils.redaction import redact_sensitive_data
from app.services.audit_service import AuditService
from app.services.audit_integrity_service import AuditIntegrityService
from app.database.models.audit_event import AuditEvent

def test_recursive_redaction_sanitizes_secrets():
    """
    Security Test: Sensitive keys are redacted recursively while preserving non-sensitive fields.
    """
    raw_payload = {
        "password": "SuperSecretPassword123!",
        "api_key": "rzp_test_secret_key_9999",
        "webhook_secret": "whsec_supersecret_abc",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "user": {
            "name": "Jane Merchant",
            "email": "jane@merchant.test",
            "access_token": "token_12345",
            "card_details": {
                "card_number": "4111111111111111",
                "cvv": "123",
                "expiry": "12/28"
            }
        },
        "safe_data": {
            "currency": "INR",
            "token_usage": 150,
            "product_id": "prod_123",
            "amount": "3499.00"
        }
    }

    sanitized = redact_sensitive_data(raw_payload)

    # Verify sensitive fields are masked
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["webhook_secret"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["user"]["access_token"] == "[REDACTED]"
    assert sanitized["user"]["card_details"]["card_number"] == "[REDACTED]"
    assert sanitized["user"]["card_details"]["cvv"] == "[REDACTED]"

    # Verify safe fields are preserved
    assert sanitized["user"]["name"] == "Jane Merchant"
    assert sanitized["safe_data"]["currency"] == "INR"
    assert sanitized["safe_data"]["token_usage"] == 150
    assert sanitized["safe_data"]["amount"] == "3499.00"

def test_audit_event_persists_redacted_payload_and_hashes_redacted_data(db: Session, setup_test_data):
    """
    Security Test: Audit events never store raw secrets in the database or hash payloads.
    """
    m1_id = setup_test_data["m1"]
    trace_id = "trc_redact_test_01"

    event = AuditService.record_event(
        db=db,
        merchant_id=m1_id,
        trace_id=trace_id,
        actor_type="USER",
        action="LOGIN_ATTEMPT",
        event_type="AUTH",
        metadata_json={
            "password": "plaintext_password_that_must_not_leak",
            "token": "sensitive_jwt_token",
            "currency": "INR"
        }
    )
    db.commit()

    # Query directly from DB
    persisted = db.query(AuditEvent).filter(AuditEvent.id == event.id).first()
    assert "plaintext_password" not in str(persisted.metadata_json)
    assert persisted.metadata_json["password"] == "[REDACTED]"
    assert persisted.metadata_json["token"] == "[REDACTED]"
    assert persisted.metadata_json["currency"] == "INR"

    # Integrity verification must succeed against the stored redacted metadata
    integrity = AuditIntegrityService.verify_trace(db, trace_id, m1_id)
    assert integrity["is_valid"] is True

def test_cross_merchant_trace_access_prohibited(client: TestClient, db: Session, setup_test_data):
    """
    Security Test: A client with merchant 2 context cannot access merchant 1's trace.
    """
    m1_id = setup_test_data["m1"]
    m2_id = setup_test_data["m2"]
    trace_id = "trc_cross_sec_01"

    AuditService.record_event(
        db=db,
        merchant_id=m1_id,
        trace_id=trace_id,
        actor_type="SYSTEM",
        action="CONFIDENTIAL_TRANSACTION",
        event_type="SETTLEMENT",
        status="SUCCESS"
    )
    db.commit()

    # Attempt access with merchant 2
    res = client.get(f"/api/v1/audit/traces/{trace_id}?merchant_id={m2_id}")
    assert res.status_code == 404
