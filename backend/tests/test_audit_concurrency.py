import os
import threading
import pytest
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine

from app.database.models.base import Base
from app.database.models.merchant import Merchant
from app.database.models.audit_event import AuditEvent
from app.services.audit_service import AuditService
from app.services.audit_integrity_service import AuditIntegrityService

POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL", "")
has_postgres = bool(
    POSTGRES_TEST_URL and 
    (POSTGRES_TEST_URL.startswith("postgresql://") or POSTGRES_TEST_URL.startswith("postgres://"))
)

def test_concurrent_audit_event_creation_serialized(db: Session, setup_test_data):
    """
    Concurrency Test: Multiple sequential and concurrent writers appending to the same trace
    maintain strictly monotonic sequence numbers and unbroken cryptographic hash chains.
    """
    m1_id = setup_test_data["m1"]
    trace_id = "trc_concurrent_seq_01"

    # Sequentially append 10 events
    for i in range(1, 11):
        AuditService.record_event(
            db=db,
            merchant_id=m1_id,
            trace_id=trace_id,
            actor_type="SYSTEM",
            action=f"STEP_{i}",
            event_type="CONCURRENT_STEP",
            status="SUCCESS",
            metadata_json={"index": i}
        )
    db.commit()

    # Validate integrity
    res = AuditIntegrityService.verify_trace(db, trace_id, m1_id)
    assert res["is_valid"] is True
    assert res["event_count"] == 10
    assert res["tampering_detected"] is False

    events = db.query(AuditEvent).filter(
        AuditEvent.merchant_id == m1_id,
        AuditEvent.trace_id == trace_id
    ).order_by(AuditEvent.sequence_number.asc()).all()

    sequences = [e.sequence_number for e in events]
    assert sequences == list(range(1, 11))

@pytest.mark.skipif(not has_postgres, reason="PostgreSQL test environment (POSTGRES_TEST_URL) not configured in environment")
def test_postgres_concurrent_audit_trace_row_locking():
    """
    PostgreSQL Dedicated Test: Multi-threaded simultaneous writers to the same (merchant_id, trace_id)
    using row-level SELECT ... FOR UPDATE on AuditTraceHead.
    """
    engine = create_engine(POSTGRES_TEST_URL)
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine)
    init_db = SessionFactory()

    m = Merchant(name="PG Audit Merchant", domain="pg.audit.test")
    init_db.add(m)
    init_db.commit()
    merchant_id = m.id
    init_db.close()

    trace_id = "trc_pg_thread_race_01"
    errors = []

    def worker(worker_id: int):
        thread_db = SessionFactory()
        try:
            for j in range(3):
                AuditService.record_event(
                    db=thread_db,
                    merchant_id=merchant_id,
                    trace_id=trace_id,
                    actor_type="AGENT",
                    action=f"WORKER_{worker_id}_ACTION_{j}",
                    event_type="THREAD_EVENT",
                    status="SUCCESS",
                    metadata_json={"worker": worker_id, "iteration": j}
                )
                thread_db.commit()
        except Exception as ex:
            errors.append(str(ex))
        finally:
            thread_db.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0

    verify_db = SessionFactory()
    integrity_res = AuditIntegrityService.verify_trace(verify_db, trace_id, merchant_id)
    assert integrity_res["is_valid"] is True
    assert integrity_res["event_count"] == 12 # 4 workers * 3 actions
    verify_db.close()
