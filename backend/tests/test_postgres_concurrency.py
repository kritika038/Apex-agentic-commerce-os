import os
import json
import threading
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models.base import Base
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.payment_transaction import PaymentTransaction
from app.payments.service import PaymentService
from app.payments.reconciliation import PaymentReconciliation
from app.payments.state_machine import PaymentState

POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL", "")

has_postgres = bool(
    POSTGRES_TEST_URL and 
    (POSTGRES_TEST_URL.startswith("postgresql://") or POSTGRES_TEST_URL.startswith("postgres://"))
)

@pytest.mark.skipif(not has_postgres, reason="PostgreSQL test environment (POSTGRES_TEST_URL) not configured in environment")
def test_postgres_concurrent_reconciliation():
    """
    PostgreSQL Row-Locking Test: Two concurrent threads execute with_for_update() row locking
    on the same UNKNOWN PaymentTransaction. State machine resolves deterministically without duplicate mutations.
    """
    engine = create_engine(POSTGRES_TEST_URL)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    m = Merchant(name="PG Merchant", domain="pg.test")
    db.add(m)
    db.commit()

    tx = PaymentTransaction(
        merchant_id=m.id,
        purchase_intent_id="pi_pg_001",
        authorization_id="auth_pg_001",
        amount=Decimal("3499.00"),
        currency="INR",
        status=PaymentState.UNKNOWN,
        idempotency_key="idemp_pg_rec_01",
        receipt="rcpt_pg_01"
    )
    db.add(tx)
    db.commit()
    tx_id = tx.id
    db.close()

    mock_provider = PaymentService.get_mock_provider()
    results = []

    def recon_worker():
        worker_db = Session()
        try:
            res_tx = PaymentReconciliation.reconcile_transaction(
                db=worker_db,
                transaction_id=tx_id,
                merchant_id=m.id,
                provider_override=mock_provider
            )
            results.append(res_tx.status)
        finally:
            worker_db.close()

    t1 = threading.Thread(target=recon_worker)
    t2 = threading.Thread(target=recon_worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    verify_db = Session()
    final_tx = verify_db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert final_tx.status in (PaymentState.FAILED, PaymentState.CAPTURED, PaymentState.ORDER_CREATED)
    verify_db.close()

@pytest.mark.skipif(not has_postgres, reason="PostgreSQL test environment (POSTGRES_TEST_URL) not configured in environment")
def test_postgres_concurrent_duplicate_order_creation():
    """
    PostgreSQL Unique Constraint Test: Two concurrent threads attempt create_payment_order
    with identical (merchant_id, idempotency_key). Unique index prevents duplicate rows.
    """
    engine = create_engine(POSTGRES_TEST_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    m = Merchant(name="PG Merchant 2", domain="pg2.test")
    db.add(m)
    db.commit()

    p = Product(merchant_id=m.id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running")
    db.add(p)
    db.commit()

    auth = TransactionAuthorization(
        merchant_id=m.id,
        purchase_intent_id="pi_pg_race",
        policy_evaluation_id="eval_pg_race",
        policy_version=1,
        authorized_amount=Decimal("3499.00"),
        currency="INR",
        status="AUTHORIZED",
        authorized_by="POLICY_ENGINE_AUTO",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=15)
    )
    db.add(auth)
    db.commit()

    idemp_key = "idemp_pg_race_key"
    mock_provider = PaymentService.get_mock_provider()
    created_ids = []

    def create_worker():
        worker_db = Session()
        try:
            tx = PaymentService.create_payment_order(
                db=worker_db,
                merchant_id=m.id,
                purchase_intent_id="pi_pg_race",
                authorization_id=auth.id,
                idempotency_key=idemp_key,
                provider_override=mock_provider
            )
            created_ids.append(tx.id)
        finally:
            worker_db.close()

    t1 = threading.Thread(target=create_worker)
    t2 = threading.Thread(target=create_worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Both returned same transaction ID
    assert len(created_ids) == 2
    assert created_ids[0] == created_ids[1]

    # Database count is exactly 1
    verify_db = Session()
    count = verify_db.query(PaymentTransaction).filter(
        PaymentTransaction.merchant_id == m.id,
        PaymentTransaction.idempotency_key == idemp_key
    ).count()
    assert count == 1
    verify_db.close()
