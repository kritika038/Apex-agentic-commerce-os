from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.payment_attempt import PaymentAttempt
from app.database.models.reconciliation_attempt import ReconciliationAttempt
from app.auth.deps import get_current_user, get_optional_current_user
from app.schemas.payment import (
    PaymentCreateOrderRequest,
    PaymentOrderResponse,
    PaymentTransactionResponse,
    PaymentReconcileResponse,
    MockPaymentSimulateRequest,
    PaymentVerifySignatureRequest,
    PaymentConfigResponse
)
from app.schemas.recovery import (
    PaymentAttemptResponse,
    ReconciliationAttemptResponse,
    TimelineEventResponse,
    SimulatorScenarioRequest,
    SimulatorScenarioResponse
)
from app.payments.service import PaymentService
from app.payments.reconciliation import PaymentReconciliation
from app.payments.simulator import PaymentSimulator
from app.payments.state_machine import PaymentState
from app.payments.razorpay_provider import RazorpayProvider
from app.payments.utils import to_minor_units
from app.core.config import settings

router = APIRouter(tags=["Payments"])

def _resolve_merchant_id(current_user: Optional[User], db: Session, merchant_id: Optional[str] = None) -> str:
    if current_user and current_user.merchant_id:
        return current_user.merchant_id
    if merchant_id:
        m = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if m:
            return m.id
    m = db.query(Merchant).first()
    if m:
        return m.id
    raise HTTPException(status_code=400, detail="Merchant context not found.")

@router.get("/config", response_model=PaymentConfigResponse)
def get_payment_configuration():
    """
    Returns public Razorpay configuration for frontend checkout integration.
    Never exposes API secrets or webhook secrets.
    """
    is_configured = bool(
        settings.RAZORPAY_KEY_ID
        and settings.RAZORPAY_KEY_SECRET
        and not settings.RAZORPAY_KEY_ID.startswith("your_")
        and not "xxxx" in settings.RAZORPAY_KEY_ID
    )
    provider_type = "razorpay" if (is_configured and settings.PAYMENT_PROVIDER != "mock") else settings.PAYMENT_PROVIDER
    return PaymentConfigResponse(
        configured=is_configured,
        key_id=settings.RAZORPAY_KEY_ID if is_configured else None,
        mode=settings.RAZORPAY_MODE or "test",
        provider=provider_type,
        currency="INR"
    )

@router.post("/create-order", response_model=PaymentOrderResponse)
@router.post("/orders", response_model=PaymentOrderResponse)
def create_payment_order(
    payload: PaymentCreateOrderRequest,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Creates a Payment Order via PaymentProvider after strictly verifying the TransactionAuthorization.
    Server derives amount and currency from the authorization snapshot; client input amounts are rejected.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    idempotency_key = payload.idempotency_key or f"idem_{payload.purchase_intent_id[:8]}_{payload.authorization_id[:8]}"
    tx = PaymentService.create_payment_order(
        db=db,
        merchant_id=m_id,
        purchase_intent_id=payload.purchase_intent_id,
        authorization_id=payload.authorization_id,
        idempotency_key=idempotency_key,
        expected_amount=payload.expected_amount,
        expected_currency=payload.expected_currency
    )
    is_razorpay_configured = bool(
        settings.RAZORPAY_KEY_ID
        and settings.RAZORPAY_KEY_SECRET
        and not settings.RAZORPAY_KEY_ID.startswith("your_")
        and not "xxxx" in settings.RAZORPAY_KEY_ID
    )
    public_key_id = settings.RAZORPAY_KEY_ID if is_razorpay_configured else None

    return PaymentOrderResponse(
        payment_transaction_id=tx.id,
        razorpay_order_id=tx.razorpay_order_id,
        razorpay_key_id=public_key_id,
        key_id=public_key_id,
        amount=tx.amount,
        amount_minor=to_minor_units(tx.amount, tx.currency),
        currency=tx.currency,
        status=tx.status,
        receipt=tx.receipt,
        created_at=tx.created_at
    )

@router.post("/verify-signature", response_model=PaymentTransactionResponse)
@router.post("/verify", response_model=PaymentTransactionResponse)
def verify_payment_signature(
    payload: PaymentVerifySignatureRequest,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Cryptographic verification endpoint for Razorpay Checkout return data.
    Validates HMAC-SHA256 signature using RAZORPAY_KEY_SECRET before marking the transaction as CAPTURED.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id) if current_user else None
    tx = PaymentService.verify_payment_signature(
        db=db,
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_signature=payload.razorpay_signature,
        merchant_id=m_id
    )
    return tx

@router.get("", response_model=List[PaymentTransactionResponse])
def list_payment_transactions(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    transactions = db.query(PaymentTransaction).filter(
        PaymentTransaction.merchant_id == m_id
    ).order_by(PaymentTransaction.created_at.desc()).all()
    return transactions

@router.get("/recovery/failures", response_model=List[PaymentTransactionResponse])
def list_recovery_failures(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Returns transactions that are in UNKNOWN, RECONCILING, or FAILED state for the Recovery Dashboard.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    transactions = db.query(PaymentTransaction).filter(
        PaymentTransaction.merchant_id == m_id,
        PaymentTransaction.status.in_([PaymentState.UNKNOWN, PaymentState.RECONCILING, PaymentState.FAILED])
    ).order_by(PaymentTransaction.created_at.desc()).all()
    return transactions

@router.post("/simulator/scenario", response_model=SimulatorScenarioResponse)
def trigger_simulator_scenario(
    payload: SimulatorScenarioRequest,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Deterministic failure simulator endpoint. Restricted to development/test/demo mode.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    res = PaymentSimulator.execute_scenario(
        db=db,
        scenario=payload.scenario,
        merchant_id=m_id,
        transaction_id=payload.transaction_id,
        purchase_intent_id=payload.purchase_intent_id,
        authorization_id=payload.authorization_id
    )
    return SimulatorScenarioResponse(**res)

@router.get("/{id}", response_model=PaymentTransactionResponse)
def get_payment_transaction(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    return PaymentService.get_payment_transaction(db, transaction_id=id, merchant_id=m_id)

@router.post("/{id}/reconcile", response_model=PaymentReconcileResponse)
def reconcile_payment(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    tx = PaymentService.get_payment_transaction(db, transaction_id=id, merchant_id=m_id)
    prev_status = tx.status
    provider = PaymentService.get_provider()
    reconciled_tx = PaymentReconciliation.reconcile_transaction(
        db=db,
        transaction_id=id,
        merchant_id=m_id,
        provider_override=provider
    )
    return PaymentReconcileResponse(
        transaction_id=reconciled_tx.id,
        previous_status=prev_status,
        current_status=reconciled_tx.status,
        reconciled_via="GATEWAY_POLL",
        message=f"Transaction reconciled from '{prev_status}' to '{reconciled_tx.status}'."
    )

@router.get("/{id}/attempts", response_model=List[PaymentAttemptResponse])
def get_payment_attempts(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    # verify ownership
    PaymentService.get_payment_transaction(db, transaction_id=id, merchant_id=m_id)
    attempts = db.query(PaymentAttempt).filter(
        PaymentAttempt.payment_transaction_id == id,
        PaymentAttempt.merchant_id == m_id
    ).order_by(PaymentAttempt.attempt_number.asc()).all()
    return attempts

@router.get("/{id}/reconciliations", response_model=List[ReconciliationAttemptResponse])
def get_reconciliation_attempts(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    PaymentService.get_payment_transaction(db, transaction_id=id, merchant_id=m_id)
    recons = db.query(ReconciliationAttempt).filter(
        ReconciliationAttempt.payment_transaction_id == id,
        ReconciliationAttempt.merchant_id == m_id
    ).order_by(ReconciliationAttempt.attempt_number.asc()).all()
    return recons

@router.get("/{id}/timeline", response_model=List[TimelineEventResponse])
def get_transaction_timeline(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Generates a database-backed chronological event timeline from PaymentAttempt, ReconciliationAttempt,
    and state transition timestamps.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    tx = PaymentService.get_payment_transaction(db, transaction_id=id, merchant_id=m_id)

    events: List[TimelineEventResponse] = []

    # 1. Transaction Initialized
    events.append(TimelineEventResponse(
        timestamp=tx.created_at,
        event_type="TRANSACTION_INITIALIZED",
        title="Transaction Created",
        description=f"Transaction initialized for Intent {tx.purchase_intent_id[:8]} with Authoritative Amount ₹{float(tx.amount):,.2f} {tx.currency}.",
        badge_variant="info",
        metadata={"receipt": tx.receipt, "idempotency_key": tx.idempotency_key}
    ))

    # 2. Payment Attempts
    attempts = db.query(PaymentAttempt).filter(
        PaymentAttempt.payment_transaction_id == id
    ).order_by(PaymentAttempt.started_at.asc()).all()

    for att in attempts:
        variant = "success" if att.status == "SUCCESS" else "error" if att.status in ("TIMEOUT", "FAILED", "PROVIDER_ERROR") else "warning"
        events.append(TimelineEventResponse(
            timestamp=att.started_at,
            event_type=f"PROVIDER_{att.operation}",
            title=f"Provider Call: {att.operation} ({att.provider.upper()})",
            description=f"Status: {att.status}. {att.error_message or ('Order ID: ' + (att.provider_order_id or 'N/A'))}",
            badge_variant=variant,
            metadata={"attempt_number": att.attempt_number, "error_code": att.error_code}
        ))

    # 3. Reconciliation Attempts
    recons = db.query(ReconciliationAttempt).filter(
        ReconciliationAttempt.payment_transaction_id == id
    ).order_by(ReconciliationAttempt.started_at.asc()).all()

    for rec in recons:
        variant = "success" if rec.resolved_status == PaymentState.CAPTURED else "error" if rec.resolved_status == PaymentState.FAILED else "warning"
        events.append(TimelineEventResponse(
            timestamp=rec.started_at,
            event_type="RECONCILIATION_EVALUATION",
            title=f"Reconciliation Attempt #{rec.attempt_number}",
            description=f"Resolved '{rec.previous_status}' → '{rec.resolved_status}'. Reason: {rec.reason}",
            badge_variant=variant,
            metadata={"provider_status": rec.provider_status, "response_hash": rec.provider_response_hash}
        ))

    # 4. Captured Timestamp
    if tx.captured_at:
        events.append(TimelineEventResponse(
            timestamp=tx.captured_at,
            event_type="PAYMENT_CAPTURED",
            title="Payment Captured & Settled",
            description=f"Transaction marked CAPTURED with Gateway Payment ID {tx.razorpay_payment_id or 'pay_confirmed'}.",
            badge_variant="success",
            metadata={"payment_id": tx.razorpay_payment_id}
        ))

    # 5. Failed Timestamp
    if tx.failed_at and tx.status == PaymentState.FAILED:
        events.append(TimelineEventResponse(
            timestamp=tx.failed_at,
            event_type="PAYMENT_FAILED",
            title="Payment Failed",
            description=f"Terminal state FAILED. Code: {tx.failure_code or 'UNKNOWN'}, Message: {tx.failure_message or 'No details'}.",
            badge_variant="error",
            metadata={"failure_code": tx.failure_code}
        ))

    # Sort strictly chronologically
    events.sort(key=lambda x: x.timestamp)
    return events

@router.post("/{id}/simulate-mock", response_model=PaymentTransactionResponse)
def simulate_mock_payment(
    id: str,
    payload: MockPaymentSimulateRequest,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Simulates gateway payment completion strictly when the backend is configured in MOCK PAYMENT MODE.
    The server initiates simulation via MockPaymentProvider and updates state; client cannot directly set status.
    """
    if settings.PAYMENT_PROVIDER != "mock" or settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mock payment simulation is disabled unless PAYMENT_PROVIDER=mock outside production."
        )

    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    tx = PaymentService.get_payment_transaction(db, transaction_id=id, merchant_id=m_id)

    mock_provider = PaymentService.get_mock_provider()
    if payload.outcome == "SUCCESS":
        mock_provider.simulate_payment_success(
            order_id=tx.razorpay_order_id or "order_mock_fallback",
            amount_minor=int(tx.amount * 100),
            currency=tx.currency
        )
        reconciled = PaymentReconciliation.reconcile_transaction(
            db=db,
            transaction_id=id,
            merchant_id=m_id,
            provider_override=mock_provider
        )
        return reconciled
    else:
        PaymentStateMachine.transition(
            transaction=tx,
            to_state=PaymentState.FAILED,
            reason="Mock payment was failed as requested.",
            error_code="MOCK_SIMULATED_FAILURE",
            db=db
        )
        return tx
