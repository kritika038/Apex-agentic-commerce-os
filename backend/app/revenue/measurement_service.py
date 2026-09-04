from decimal import Decimal
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.database.models.revenue_opportunity import RevenueOpportunity
from app.revenue.schemas import RevenueMetricsResponse, RevenueExperimentItem

class RevenueMeasurementService:
    """
    Revenue Measurement Service:
    Tracks simulated vs. actual commercial performance metrics.
    
    Invariant:
    - Never fabricates actual revenue without real executed transactions.
    - Clearly distinguishes SIMULATED vs ACTUAL metrics.
    """

    @staticmethod
    def get_metrics(db: Session, merchant_id: str) -> RevenueMetricsResponse:
        opps = db.query(RevenueOpportunity).filter(
            RevenueOpportunity.merchant_id == merchant_id
        ).all()

        total = len(opps)
        executed = sum(1 for o in opps if o.status == "EXECUTED")
        approved = sum(1 for o in opps if o.status in ("APPROVED", "EXECUTED"))
        rejected = sum(1 for o in opps if o.status == "REJECTED")

        approval_rate = round((approved / total * 100), 1) if total > 0 else 0.0

        projected_gmv = sum((o.estimated_net_value for o in opps), Decimal("0.00"))
        actual_gmv = sum((o.estimated_net_value for o in opps if o.status == "EXECUTED"), Decimal("0.00"))

        return RevenueMetricsResponse(
            total_opportunities=total,
            projected_incremental_gmv=projected_gmv,
            actual_incremental_gmv=actual_gmv,
            approval_rate=approval_rate,
            executed_campaigns=executed,
            policy_blocks=rejected,
            measurement_status="SIMULATION_BENCHMARK_ACTIVE"
        )

    @staticmethod
    def get_experiments(db: Session, merchant_id: str) -> List[RevenueExperimentItem]:
        opps = db.query(RevenueOpportunity).filter(
            RevenueOpportunity.merchant_id == merchant_id
        ).order_by(RevenueOpportunity.created_at.desc()).all()

        items: List[RevenueExperimentItem] = []
        for o in opps:
            items.append(RevenueExperimentItem(
                opportunity_id=o.id,
                title=o.title,
                type=o.type,
                status=o.status,
                simulated_net_value=o.estimated_net_value,
                actual_orders=o.estimated_incremental_orders if o.status == "EXECUTED" else 0,
                actual_gmv=o.estimated_net_value if o.status == "EXECUTED" else Decimal("0.00"),
                executed_at=o.executed_at,
                measurement_status="ACTUAL_EXECUTED" if o.status == "EXECUTED" else "SIMULATED_PROJECTION"
            ))

        return items
