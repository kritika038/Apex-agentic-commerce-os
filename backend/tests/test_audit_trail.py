import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.database.models.merchant import Merchant
from app.database.models.audit_event import AuditEvent
from app.services.audit_service import AuditService
from app.services.audit_integrity_service import AuditIntegrityService, GENESIS_HASH

def test_audit_event_creation_and_ordering(db: Session, setup_test_data):
    """
    Test: Audit events are created with strictly monotonic sequence numbers
    and unbroken SHA-256 hash chains.
    """
    m1_id = setup_test_data["m1"]
    trace_id = "trc_test_order_001"

    e1 = AuditService.record_event(
        db=db,
        merchant_id=m1_id,
        trace_id=trace_id,
        actor_type="USER",
        action="AI_REQUEST",
        event_type="AI_REQUEST",
        status="SUCCESS",
        metadata_json={"query": "running shoes"}
    )

    e2 = AuditService.record_event(
        db=db,
        merchant_id=m1_id,
        trace_id=trace_id,
        actor_type="AGENT",
        action="search_products",
        event_type="TOOL_EXECUTION",
        tool_name="search_products",
        status="SUCCESS",
        metadata_json={"count": 3}
    )

    e3 = AuditService.record_event(
        db=db,
        merchant_id=m1_id,
        trace_id=trace_id,
        actor_type="SYSTEM",
        action="EVALUATE_POLICY",
        event_type="POLICY_EVALUATION",
        decision="ALLOW",
        risk_level="LOW",
        status="SUCCESS"
    )
    db.commit()

    assert e1.sequence_number == 1
    assert e2.sequence_number == 2
    assert e3.sequence_number == 3

    assert e1.previous_event_hash == GENESIS_HASH
    assert e2.previous_event_hash == e1.event_hash
    assert e3.previous_event_hash == e2.event_hash

    # Verify integrity
    integrity = AuditIntegrityService.verify_trace(db, trace_id, m1_id)
    assert integrity["is_valid"] is True
    assert integrity["event_count"] == 3
    assert integrity["tampering_detected"] is False

def test_audit_trail_tenant_isolation(client: TestClient, db: Session, setup_test_data):
    """
    Security Test: Merchant 2 cannot view or search Merchant 1's audit events or traces.
    """
    m1_id = setup_test_data["m1"]
    m2_id = setup_test_data["m2"]
    trace_id = "trc_m1_isolated_001"

    AuditService.record_event(
        db=db,
        merchant_id=m1_id,
        trace_id=trace_id,
        actor_type="USER",
        action="AI_REQUEST",
        event_type="AI_REQUEST",
        status="SUCCESS"
    )
    db.commit()

    # Query trace under merchant 2 -> 404
    res = client.get(f"/api/v1/audit/traces/{trace_id}?merchant_id={m2_id}")
    assert res.status_code == 404

    # Query events list under merchant 2 -> empty list
    res_list = client.get(f"/api/v1/audit/events?merchant_id={m2_id}&trace_id={trace_id}")
    assert res_list.status_code == 200
    assert res_list.json()["total"] == 0

def test_audit_event_pagination_and_filters(client: TestClient, db: Session, setup_test_data):
    """
    Test: Audit event list endpoint supports pagination, actor_type, and status filters.
    """
    m1_id = setup_test_data["m1"]
    trace_id = "trc_page_001"

    for i in range(15):
        AuditService.record_event(
            db=db,
            merchant_id=m1_id,
            trace_id=trace_id,
            actor_type="AGENT" if i % 2 == 0 else "SYSTEM",
            action=f"ACTION_{i}",
            event_type="OPERATION",
            status="SUCCESS" if i != 10 else "FAILED"
        )
    db.commit()

    # Pagination: page 1 with page_size=5
    res = client.get(f"/api/v1/audit/events?merchant_id={m1_id}&trace_id={trace_id}&page=1&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 15
    assert len(data["items"]) == 5
    assert data["total_pages"] == 3

    # Filter by status="FAILED"
    res_failed = client.get(f"/api/v1/audit/events?merchant_id={m1_id}&trace_id={trace_id}&status=FAILED")
    assert res_failed.status_code == 200
    assert res_failed.json()["total"] == 1
    assert res_failed.json()["items"][0]["action"] == "ACTION_10"

def test_audit_api_contract_envelope_and_empty_response(client: TestClient, db: Session, setup_test_data):
    """
    Contract Test: Audit event endpoint strictly returns PaginatedAuditEvents envelope with items list,
    total count, pagination metadata, and never malformed types even when empty.
    """
    m2_id = setup_test_data["m2"]
    res = client.get(f"/api/v1/audit/events?merchant_id={m2_id}&trace_id=trc_non_existent")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 0
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 50
    assert data["total_pages"] == 1

