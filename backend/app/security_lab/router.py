from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.database.models.security_attack_result import SecurityAttackResult
from app.auth.deps import get_optional_current_user
from app.security_lab.schemas import (
    AttackScenarioDefinition,
    SecurityAttackExecutionResponse,
    SecurityLabSummaryResponse
)
from app.security_lab.attack_runner import RedTeamAttackRunner

router = APIRouter(prefix="/security-lab", tags=["AI Red-Team Security Lab"])

def _resolve_merchant(db: Session, merchant_id: Optional[str], current_user: Optional[User]) -> str:
    if current_user and current_user.merchant_id:
        return current_user.merchant_id
    if merchant_id:
        m = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if m:
            return m.id
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target merchant '{merchant_id}' not found."
        )
    m = db.query(Merchant).filter(Merchant.is_active == True).first()
    if m:
        return m.id
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Merchant context required."
    )

@router.get("/scenarios", response_model=List[AttackScenarioDefinition])
def get_attack_scenarios():
    """
    Returns the comprehensive catalog of 12 red-team attack scenarios.
    """
    return RedTeamAttackRunner.get_catalog()

@router.post("/run-all", response_model=SecurityLabSummaryResponse)
def run_all_security_attacks(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Executes the entire 12-attack red-team verification suite against production security boundaries.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    return RedTeamAttackRunner.run_all(db=db, merchant_id=m_id)

@router.post("/run/{scenario_id}", response_model=SecurityAttackExecutionResponse)
def run_single_security_attack(
    scenario_id: str,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Executes a single specific attack scenario through the live control plane.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    return RedTeamAttackRunner.run_scenario(db=db, merchant_id=m_id, scenario_id=scenario_id)

@router.get("/results", response_model=List[SecurityAttackExecutionResponse])
def get_security_attack_results(
    merchant_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Lists historical security attack execution results for the merchant.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    results = db.query(SecurityAttackResult).filter(
        SecurityAttackResult.merchant_id == m_id
    ).order_by(SecurityAttackResult.created_at.desc()).limit(limit).all()

    return [
        SecurityAttackExecutionResponse(
            id=r.id,
            scenario_id=r.scenario_id,
            scenario_name=r.scenario_name,
            attempted_payload=r.request_payload_redacted or {},
            expected_result=r.expected_result,
            actual_result=r.actual_result,
            blocked=r.blocked,
            block_layer=r.block_layer,
            reason=r.reason,
            trace_id=r.trace_id,
            executed_at=r.created_at
        )
        for r in results
    ]
