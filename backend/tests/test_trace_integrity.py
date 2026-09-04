import pytest
from sqlalchemy.orm import Session
from app.services.audit_service import AuditService
from app.services.audit_integrity_service import AuditIntegrityService
from app.database.models.audit_event import AuditEvent

def _create_sample_trace(db: Session, merchant_id: str, trace_id: str, count: int = 4):
    for i in range(1, count + 1):
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=trace_id,
            actor_type="SYSTEM",
            action=f"ACTION_{i}",
            event_type="LIFECYCLE_STEP",
            status="SUCCESS",
            metadata_json={"step": i}
        )
    db.commit()

def test_unbroken_trace_integrity_validation(db: Session, setup_test_data):
    """
    Test: A pristine, unmodified sequence of audit events passes hash chain validation.
    """
    m1_id = setup_test_data["m1"]
    trace_id = "trc_pristine_001"
    _create_sample_trace(db, m1_id, trace_id, count=5)

    res = AuditIntegrityService.verify_trace(db, trace_id, m1_id)
    assert res["is_valid"] is True
    assert res["event_count"] == 5
    assert res["tampering_detected"] is False

def test_detect_modified_event_payload(db: Session, setup_test_data):
    """
    Tamper Detection Test: Modifying an event's action or metadata breaks the SHA-256 hash.
    """
    m1_id = setup_test_data["m1"]
    trace_id = "trc_tamper_mod_01"
    _create_sample_trace(db, m1_id, trace_id, count=4)

    # Tamper with event 2
    event2 = db.query(AuditEvent).filter(
        AuditEvent.merchant_id == m1_id,
        AuditEvent.trace_id == trace_id,
        AuditEvent.sequence_number == 2
    ).first()
    event2.action = "TAMPERED_MALICIOUS_ACTION"
    db.commit()

    res = AuditIntegrityService.verify_trace(db, trace_id, m1_id)
    assert res["is_valid"] is False
    assert res["tampering_detected"] is True
    assert res["first_invalid_event_id"] == event2.id
    assert "Payload modification detected" in res["detail"]

def test_detect_deleted_event_gap(db: Session, setup_test_data):
    """
    Tamper Detection Test: Deleting an event in the middle creates a sequence/hash gap.
    """
    m1_id = setup_test_data["m1"]
    trace_id = "trc_tamper_del_01"
    _create_sample_trace(db, m1_id, trace_id, count=4)

    # Delete event 2
    event2 = db.query(AuditEvent).filter(
        AuditEvent.merchant_id == m1_id,
        AuditEvent.trace_id == trace_id,
        AuditEvent.sequence_number == 2
    ).first()
    db.delete(event2)
    db.commit()

    res = AuditIntegrityService.verify_trace(db, trace_id, m1_id)
    assert res["is_valid"] is False
    assert res["tampering_detected"] is True
    assert "Sequence gap" in res["detail"] or "Broken hash chain" in res["detail"]

def test_detect_reordered_events(db: Session, setup_test_data):
    """
    Tamper Detection Test: Swapping the sequence numbers or positions of events is caught.
    """
    m1_id = setup_test_data["m1"]
    trace_id = "trc_tamper_reorder_01"
    _create_sample_trace(db, m1_id, trace_id, count=4)

    # Swap sequence numbers of event 2 and event 3
    e2 = db.query(AuditEvent).filter(AuditEvent.trace_id == trace_id, AuditEvent.sequence_number == 2).first()
    e3 = db.query(AuditEvent).filter(AuditEvent.trace_id == trace_id, AuditEvent.sequence_number == 3).first()
    
    # Temporarily set sequence to 99 to bypass unique constraint during swap
    e2.sequence_number = 99
    db.flush()
    e3.sequence_number = 2
    db.flush()
    e2.sequence_number = 3
    db.commit()

    res = AuditIntegrityService.verify_trace(db, trace_id, m1_id)
    assert res["is_valid"] is False
    assert res["tampering_detected"] is True
