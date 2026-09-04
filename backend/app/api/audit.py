import math
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database.session import get_db
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.database.models.audit_event import AuditEvent
from app.database.models.agent_trace import AgentTrace
from app.database.models.agent_step import AgentStep
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.recommendation import Recommendation
from app.database.models.policy_evaluation import PolicyEvaluation
from app.database.models.approval_request import ApprovalRequest
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.reconciliation_attempt import ReconciliationAttempt
from app.auth.deps import get_current_user, get_optional_current_user
from app.services.audit_service import AuditService
from app.services.audit_integrity_service import AuditIntegrityService
from app.schemas.audit import (
    AuditEventResponse,
    TraceSummaryResponse,
    PaginatedAuditEvents,
    AgentTraceResponse,
    ObservabilityMetricsResponse
)

router = APIRouter(tags=["Audit & Observability"])

def _resolve_merchant_id(current_user: Optional[User], db: Session, merchant_id: Optional[str] = None) -> str:
    if current_user and current_user.role not in ["merchant_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant Admin privileges required."
        )
    if current_user and current_user.merchant_id:
        return current_user.merchant_id
    if merchant_id:
        m = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if m:
            return m.id
    m = db.query(Merchant).first()
    if m:
        return m.id
    raise HTTPException(status_code=400, detail="Merchant not found.")

def _calculate_p95(latencies: List[float]) -> Any:
    if not latencies or len(latencies) < 3:
        return "N/A"
    sorted_lat = sorted(latencies)
    k = (len(sorted_lat) - 1) * 0.95
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_lat[int(k)], 2)
    d0 = sorted_lat[int(f)] * (c - k)
    d1 = sorted_lat[int(c)] * (k - f)
    return round(d0 + d1, 2)

@router.get("/traces/{trace_id}", response_model=TraceSummaryResponse)
def get_trace_timeline(
    trace_id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Chronological Trace Timeline & Executive Summary.
    Reconstructs the full lifecycle for a given trace_id and cryptographically
    validates the SHA-256 hash chain.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    summary = AuditService.get_trace_summary(db=db, trace_id=trace_id, merchant_id=m_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found for this merchant.")
    return summary

@router.get("/events", response_model=PaginatedAuditEvents)
def list_audit_events(
    trace_id: Optional[str] = None,
    session_id: Optional[str] = None,
    purchase_intent_id: Optional[str] = None,
    payment_transaction_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    actor_type: Optional[str] = None,
    action: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    merchant_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Paginated, filterable audit event ledger scoped strictly to authenticated merchant.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)

    query = db.query(AuditEvent).filter(AuditEvent.merchant_id == m_id)

    if trace_id:
        query = query.filter(AuditEvent.trace_id == trace_id)
    if session_id:
        query = query.filter(AuditEvent.session_id == session_id)
    if purchase_intent_id:
        query = query.filter(AuditEvent.purchase_intent_id == purchase_intent_id)
    if payment_transaction_id:
        query = query.filter(AuditEvent.payment_transaction_id == payment_transaction_id)
    if agent_id:
        query = query.filter(AuditEvent.agent_id == agent_id)
    if actor_type:
        query = query.filter(AuditEvent.actor_type == actor_type)
    if action:
        query = query.filter(AuditEvent.action == action)
    if status_filter:
        query = query.filter(AuditEvent.status == status_filter)

    total = query.count()
    items = query.order_by(AuditEvent.created_at.desc(), AuditEvent.sequence_number.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return PaginatedAuditEvents(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

@router.get("/agents/{agent_id}/traces", response_model=List[AgentTraceResponse])
def get_agent_traces(
    agent_id: str,
    merchant_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Retrieves detailed execution traces and step timelines for an agent.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    traces = db.query(AgentTrace).filter(
        AgentTrace.agent_id == agent_id,
        AgentTrace.merchant_id == m_id
    ).order_by(AgentTrace.created_at.desc()).limit(limit).all()

    return traces

@router.get("/metrics", response_model=ObservabilityMetricsResponse)
def get_observability_metrics(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Authoritative observability metrics derived purely from database records.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)

    # 1. Commerce Metrics
    intents = db.query(PurchaseIntent).filter(PurchaseIntent.merchant_id == m_id).all()
    intents_created = len(intents)
    intents_expired = sum(1 for i in intents if i.status == "EXPIRED")
    intents_completed = sum(1 for i in intents if i.status == "COMPLETED")

    recs = db.query(Recommendation).filter(Recommendation.merchant_id == m_id).all()
    recs_total = len(recs)
    recs_accepted = sum(1 for r in recs if r.status == "ACCEPTED")
    recs_rejected = sum(1 for r in recs if r.status == "REJECTED")
    rec_acceptance_rate = round((recs_accepted / recs_total * 100), 2) if recs_total > 0 else 0.0

    commerce_metrics = {
        "purchase_intents_created": intents_created,
        "purchase_intents_expired": intents_expired,
        "purchase_intents_completed": intents_completed,
        "recommendations_generated": recs_total,
        "recommendations_accepted": recs_accepted,
        "recommendations_rejected": recs_rejected,
        "recommendation_acceptance_rate": rec_acceptance_rate
    }

    # 2. Policy Metrics
    evals = db.query(PolicyEvaluation).filter(PolicyEvaluation.merchant_id == m_id).all()
    policy_allow = sum(1 for e in evals if e.decision == "ALLOW")
    policy_req_appr = sum(1 for e in evals if e.decision == "REQUIRES_APPROVAL")
    policy_deny = sum(1 for e in evals if e.decision == "DENY")
    risk_low = sum(1 for e in evals if e.risk_level == "LOW")
    risk_med = sum(1 for e in evals if e.risk_level == "MEDIUM")
    risk_high = sum(1 for e in evals if e.risk_level == "HIGH")

    policy_metrics = {
        "total_evaluations": len(evals),
        "allow_count": policy_allow,
        "requires_approval_count": policy_req_appr,
        "deny_count": policy_deny,
        "risk_distribution": {
            "low": risk_low,
            "medium": risk_med,
            "high": risk_high
        }
    }

    # 3. Approval Metrics
    apprs = db.query(ApprovalRequest).filter(ApprovalRequest.merchant_id == m_id).all()
    apprs_pending = sum(1 for a in apprs if a.status == "PENDING")
    apprs_approved = sum(1 for a in apprs if a.status == "APPROVED")
    apprs_rejected = sum(1 for a in apprs if a.status == "REJECTED")
    apprs_expired = sum(1 for a in apprs if a.status == "EXPIRED")

    approval_metrics = {
        "total_requests": len(apprs),
        "pending": apprs_pending,
        "approved": apprs_approved,
        "rejected": apprs_rejected,
        "expired": apprs_expired
    }

    # 4. Payment Metrics
    txs = db.query(PaymentTransaction).filter(PaymentTransaction.merchant_id == m_id).all()
    tx_created = sum(1 for t in txs if t.status == "ORDER_CREATED")
    tx_captured = sum(1 for t in txs if t.status == "CAPTURED")
    tx_failed = sum(1 for t in txs if t.status == "FAILED")
    tx_unknown = sum(1 for t in txs if t.status == "UNKNOWN")
    
    recons = db.query(ReconciliationAttempt).filter(ReconciliationAttempt.merchant_id == m_id).all()
    recons_total = len(recons)
    recons_resolved = sum(1 for r in recons if r.resolved_status in ("CAPTURED", "FAILED", "ORDER_CREATED"))
    recon_rate = round((recons_resolved / recons_total * 100), 2) if recons_total > 0 else 100.0

    payment_metrics = {
        "total_transactions": len(txs),
        "order_created": tx_created,
        "captured": tx_captured,
        "failed": tx_failed,
        "unknown": tx_unknown,
        "reconciliations_total": recons_total,
        "reconciliation_success_rate": recon_rate
    }

    # 5. Agent Metrics
    agent_traces = db.query(AgentTrace).filter(AgentTrace.merchant_id == m_id).all()
    agent_total = len(agent_traces)
    agent_succ = sum(1 for a in agent_traces if a.status == "SUCCESS")
    agent_fail = sum(1 for a in agent_traces if a.status == "FAILED")
    latencies = [a.latency_ms for a in agent_traces if a.latency_ms > 0]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    p95_lat = _calculate_p95(latencies)
    tool_calls = sum(a.tool_call_count for a in agent_traces)
    tokens = sum(a.token_usage for a in agent_traces)

    agent_metrics = {
        "total_runs": agent_total,
        "successful_runs": agent_succ,
        "failed_runs": agent_fail,
        "average_latency_ms": avg_latency,
        "p95_latency_ms": p95_lat,
        "total_tool_calls": tool_calls,
        "total_tokens_used": tokens
    }

    return ObservabilityMetricsResponse(
        commerce=commerce_metrics,
        policy=policy_metrics,
        approval=approval_metrics,
        payment=payment_metrics,
        agent=agent_metrics
    )
