from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.database.models.revenue_opportunity import RevenueOpportunity
from app.auth.deps import get_optional_current_user
from app.revenue.schemas import (
    RevenueOpportunityResponse,
    RevenueOpportunityGenerateRequest,
    RevenueSimulationRequest,
    RevenueSimulationResponse,
    RevenueOpportunityApproveRequest,
    RevenueOpportunityRejectRequest,
    RevenueOpportunityExecuteRequest,
    RevenueMetricsResponse,
    RevenueExperimentItem,
    MerchantAgentQueryRequest,
    MerchantAgentQueryResponse,
    HumanView,
    AgentView
)
from pydantic import BaseModel
from app.revenue.opportunity_engine import RevenueOpportunityEngine
from app.revenue.proposal_engine import RevenueProposalEngine
from app.revenue.simulator import RevenueSimulator
from app.revenue.campaign_service import RevenueCampaignService
from app.revenue.measurement_service import RevenueMeasurementService
from app.agents.merchant_growth_agent import MerchantGrowthAgent
from app.agents.merchant_revenue_agent import MerchantRevenueAgent

class CopilotChatRequest(BaseModel):
    message: str
    merchant_id: Optional[str] = None
    trace_id: Optional[str] = None

router = APIRouter(prefix="/revenue", tags=["Revenue Autopilot"])

def _resolve_merchant(db: Session, merchant_id: Optional[str], current_user: Optional[User]) -> str:
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

@router.post("/agent/query", response_model=MerchantAgentQueryResponse)
def merchant_agent_query_endpoint(
    payload: MerchantAgentQueryRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Conversational Merchant Revenue Agent:
    Resolves natural language queries into deterministic opportunities with Human and Agent views.
    """
    m_id = _resolve_merchant(db, payload.merchant_id, current_user)
    return MerchantRevenueAgent.handle_query(
        db=db,
        merchant_id=m_id,
        message=payload.message,
        trace_id=payload.trace_id
    )

@router.get("/opportunities", response_model=List[RevenueOpportunityResponse])
def list_revenue_opportunities(
    merchant_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Lists discovered and simulated revenue opportunities for the merchant with Human and Agent views.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    query = db.query(RevenueOpportunity).filter(RevenueOpportunity.merchant_id == m_id)
    if status_filter:
        query = query.filter(RevenueOpportunity.status == status_filter)
    opps = query.order_by(RevenueOpportunity.created_at.desc()).all()
    
    results: List[RevenueOpportunityResponse] = []
    for opp in opps:
        hv, av = RevenueOpportunityEngine.format_views(db, opp, m_id)
        resp = RevenueOpportunityResponse.model_validate(opp)
        resp.human_view = hv
        resp.agent_view = av
        results.append(resp)
    return results

@router.get("/opportunities/{id}")
def get_revenue_opportunity(
    id: str,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Retrieves revenue opportunity details and structured AI proposal breakdown.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    opp = db.query(RevenueOpportunity).filter(
        RevenueOpportunity.id == id,
        RevenueOpportunity.merchant_id == m_id
    ).first()

    if not opp:
        raise HTTPException(status_code=404, detail="Revenue opportunity not found.")

    hv, av = RevenueOpportunityEngine.format_views(db, opp, m_id)
    resp = RevenueOpportunityResponse.model_validate(opp)
    resp.human_view = hv
    resp.agent_view = av
    proposal_details = RevenueProposalEngine.format_proposal(db, opp)
    return {
        "opportunity": resp,
        "proposal_breakdown": proposal_details
    }

@router.post("/opportunities/generate", response_model=List[RevenueOpportunityResponse])
def generate_revenue_opportunities(
    payload: RevenueOpportunityGenerateRequest,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Triggers deterministic analysis of merchant catalog and inventory to discover revenue opportunities.
    """
    m_id = _resolve_merchant(db, payload.merchant_id or merchant_id, current_user)
    return RevenueOpportunityEngine.discover_opportunities(
        db=db,
        merchant_id=m_id,
        types=payload.types,
        min_confidence=payload.min_confidence or 0.70,
        trace_id=payload.trace_id
    )

@router.post("/simulate", response_model=RevenueSimulationResponse)
def simulate_revenue_opportunity(
    payload: RevenueSimulationRequest,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Runs deterministic revenue simulation and policy compliance check for a proposal.
    """
    m_id = _resolve_merchant(db, payload.merchant_id or merchant_id, current_user)
    return RevenueSimulator.simulate(db=db, merchant_id=m_id, req=payload)

@router.post("/opportunities/{id}/approve", response_model=RevenueOpportunityResponse)
def approve_revenue_opportunity(
    id: str,
    payload: RevenueOpportunityApproveRequest,
    merchant_id: Optional[str] = Query(None),
    trace_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Merchant operator approval gate for a revenue campaign.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    user_id = current_user.id if current_user else "merchant_operator"
    opp = RevenueCampaignService.approve_opportunity(
        db=db,
        merchant_id=m_id,
        opportunity_id=id,
        user_id=user_id,
        reason=payload.reason,
        trace_id=trace_id
    )
    hv, av = RevenueOpportunityEngine.format_views(db, opp, m_id)
    resp = RevenueOpportunityResponse.model_validate(opp)
    resp.human_view = hv
    resp.agent_view = av
    return resp

@router.post("/opportunities/{id}/reject", response_model=RevenueOpportunityResponse)
def reject_revenue_opportunity(
    id: str,
    payload: RevenueOpportunityRejectRequest,
    merchant_id: Optional[str] = Query(None),
    trace_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Merchant operator rejection of a revenue campaign with mandatory reason.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    user_id = current_user.id if current_user else "merchant_operator"
    opp = RevenueCampaignService.reject_opportunity(
        db=db,
        merchant_id=m_id,
        opportunity_id=id,
        user_id=user_id,
        reason=payload.reason,
        trace_id=trace_id
    )
    hv, av = RevenueOpportunityEngine.format_views(db, opp, m_id)
    resp = RevenueOpportunityResponse.model_validate(opp)
    resp.human_view = hv
    resp.agent_view = av
    return resp

@router.post("/opportunities/{id}/execute", response_model=RevenueOpportunityResponse)
def execute_revenue_opportunity(
    id: str,
    payload: RevenueOpportunityExecuteRequest,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Executes approved revenue campaign with immediate pre-execution policy and stock re-validation.
    """
    m_id = _resolve_merchant(db, payload.merchant_id or merchant_id, current_user)
    opp = RevenueCampaignService.execute_opportunity(
        db=db,
        merchant_id=m_id,
        opportunity_id=id,
        req=payload
    )
    hv, av = RevenueOpportunityEngine.format_views(db, opp, m_id)
    resp = RevenueOpportunityResponse.model_validate(opp)
    resp.human_view = hv
    resp.agent_view = av
    return resp

@router.get("/metrics", response_model=RevenueMetricsResponse)
def get_revenue_metrics(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Authoritative metrics distinguishing SIMULATED projections from ACTUAL measured uplift.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    return RevenueMeasurementService.get_metrics(db=db, merchant_id=m_id)

@router.get("/experiments", response_model=List[RevenueExperimentItem])
def get_revenue_experiments(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Lists campaign experiments and comparative benchmark performance.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    return RevenueMeasurementService.get_experiments(db=db, merchant_id=m_id)

@router.get("/overview")
def get_merchant_growth_overview(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Authoritative merchant revenue and inventory overview from real database signals.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    return MerchantGrowthAgent.get_growth_overview(db=db, merchant_id=m_id)

@router.post("/copilot/chat")
def copilot_chat(
    payload: CopilotChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Conversational Merchant AI Growth Copilot.
    """
    m_id = _resolve_merchant(db, payload.merchant_id, current_user)
    return MerchantGrowthAgent.chat(
        db=db,
        merchant_id=m_id,
        message=payload.message,
        user_id=current_user.id if current_user else None,
        trace_id=payload.trace_id
    )

@router.get("/bundles", response_model=List[RevenueOpportunityResponse])
def get_smart_bundles(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Smart Bundles discovered through real co-purchase evidence and catalog affinities.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    opps = RevenueOpportunityEngine.discover_opportunities(db=db, merchant_id=m_id, types=["BUNDLE"])
    return [o for o in opps if o.type == "BUNDLE"]

@router.get("/inventory-risk", response_model=List[RevenueOpportunityResponse])
def get_inventory_risks(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Inventory Stockout risk opportunities derived from live inventory thresholds.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    opps = RevenueOpportunityEngine.discover_opportunities(db=db, merchant_id=m_id, types=["INVENTORY_RISK"])
    return [o for o in opps if o.type == "INVENTORY_RISK"]

@router.get("/inventory/health")
def get_inventory_health(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Detailed inventory health, 14-day sales velocity, and stockout estimates.
    """
    from app.services.inventory_analytics_service import InventoryAnalyticsService
    m_id = _resolve_merchant(db, merchant_id, current_user)
    return InventoryAnalyticsService.get_inventory_health_report(db=db, merchant_id=m_id)

@router.get("/customers/segments")
def get_customer_segments(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Authoritative customer segments based on order frequency and lifetime spending.
    """
    from app.services.customer_analytics_service import CustomerAnalyticsService
    m_id = _resolve_merchant(db, merchant_id, current_user)
    return CustomerAnalyticsService.get_customer_segments(db=db, merchant_id=m_id)

@router.get("/pricing/recommendations")
def get_pricing_recommendations(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Advisory price adjustments with guardrails for merchant review.
    """
    from app.services.pricing_intelligence_service import DynamicPricingService
    m_id = _resolve_merchant(db, merchant_id, current_user)
    return DynamicPricingService.get_pricing_recommendations(db=db, merchant_id=m_id)

class PriceApplyRequest(BaseModel):
    product_id: str
    new_price: float
    reason: str
    merchant_id: Optional[str] = None

@router.post("/pricing/apply")
def apply_price_recommendation(
    payload: PriceApplyRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Applies an approved price adjustment to the product catalog and creates an audit record.
    """
    from decimal import Decimal
    from app.services.pricing_intelligence_service import DynamicPricingService
    m_id = _resolve_merchant(db, payload.merchant_id, current_user)
    user_id = current_user.id if current_user else "merchant_admin"
    prod = DynamicPricingService.apply_approved_price_change(
        db=db,
        merchant_id=m_id,
        product_id=payload.product_id,
        new_price=Decimal(str(payload.new_price)),
        approved_by_user_id=user_id,
        reason=payload.reason
    )
    return {
        "status": "SUCCESS",
        "product_id": prod.id,
        "new_price": float(prod.price),
        "message": f"Price updated to ₹{float(prod.price):,.2f}."
    }

@router.get("/risk/assess")
def assess_transaction_risk(
    amount: float = Query(2999.0),
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Advisory transaction risk score from non-sensitive transaction signals.
    """
    from decimal import Decimal
    from app.services.risk_scoring_service import RiskScoringService
    m_id = _resolve_merchant(db, merchant_id, current_user)
    return RiskScoringService.assess_transaction_risk(
        db=db,
        merchant_id=m_id,
        amount=Decimal(str(amount)),
        user_id=current_user.id if current_user else None
    )
