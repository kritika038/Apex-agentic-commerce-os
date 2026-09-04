import uuid
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.revenue_opportunity import RevenueOpportunity
from app.revenue.opportunity_engine import RevenueOpportunityEngine
from app.services.audit_service import AuditService
from app.revenue.schemas import (
    MerchantAgentQueryRequest,
    MerchantAgentQueryResponse,
    RevenueOpportunityResponse,
    HumanView,
    AgentView
)

class MerchantRevenueAgent:
    """
    Autonomous Merchant Revenue Agent & Intelligence Orchestrator:
    Formalized orchestrator coordinating deterministic analytics, basket affinity,
    revenue simulations, and governed campaign opportunities.
    
    Security & Architecture Invariants:
    - Never mutates base product prices.
    - Never fabricates metrics or numbers; returns INSUFFICIENT_DATA when sample size < 3.
    - Emits structured audit events across all lifecycle stages with unbroken trace IDs.
    - Produces synchronized Human and Agent views.
    """

    def __init__(self, db: Optional[Session] = None, merchant_id: Optional[str] = None):
        self.db = db
        self.merchant_id = merchant_id

    def process_query(self, message: str, trace_id: Optional[str] = None) -> MerchantAgentQueryResponse:
        if not self.db or not self.merchant_id:
            raise ValueError("db and merchant_id must be initialized to call process_query")
        return self.handle_query(db=self.db, merchant_id=self.merchant_id, message=message, trace_id=trace_id)

    def generate_proposals(self, min_confidence: float = 0.70, trace_id: Optional[str] = None) -> List[RevenueOpportunity]:
        if not self.db or not self.merchant_id:
            raise ValueError("db and merchant_id must be initialized to call generate_proposals")
        return RevenueOpportunityEngine.discover_opportunities(
            db=self.db,
            merchant_id=self.merchant_id,
            min_confidence=min_confidence,
            trace_id=trace_id
        )

    @classmethod
    def get_growth_overview(cls, db: Session, merchant_id: str) -> Dict[str, Any]:
        """
        Calculates authoritative sales, inventory, and opportunity metrics for the merchant.
        """
        # 1. Total Captured GMV & Orders
        captured_txs = db.query(PaymentTransaction).filter(
            PaymentTransaction.merchant_id == merchant_id,
            PaymentTransaction.status == "CAPTURED"
        ).all()

        total_gmv = sum([float(tx.amount) for tx in captured_txs], 0.0)
        total_orders = len(captured_txs)
        aov = (total_gmv / total_orders) if total_orders > 0 else 0.0

        # 2. Product Inventory & Velocity
        products = db.query(Product).filter(
            Product.merchant_id == merchant_id,
            Product.is_active == True
        ).all()

        low_stock_items = []
        in_stock_count = 0
        for p in products:
            stock = p.inventory.stock_quantity if p.inventory else 0
            if stock > 0:
                in_stock_count += 1
            if 0 < stock < 20:
                low_stock_items.append({
                    "product_id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "price": float(p.price),
                    "current_stock": stock,
                    "status": "LOW_STOCK" if stock < 10 else "ATTENTION_NEEDED"
                })

        # 3. Revenue Opportunities
        opps = db.query(RevenueOpportunity).filter(
            RevenueOpportunity.merchant_id == merchant_id
        ).all()

        active_opps = [o for o in opps if o.status in ["GENERATED", "SIMULATED", "APPROVED"]]
        executed_opps = [o for o in opps if o.status == "EXECUTED"]
        projected_inc_gmv = sum([float(o.estimated_net_value) for o in active_opps if o.estimated_net_value], 0.0)

        return {
            "total_gmv": total_gmv,
            "total_orders": total_orders,
            "average_order_value": aov,
            "catalog_size": len(products),
            "in_stock_products_count": in_stock_count,
            "low_stock_count": len(low_stock_items),
            "low_stock_items": low_stock_items,
            "active_opportunities_count": len(active_opps),
            "executed_campaigns_count": len(executed_opps),
            "projected_incremental_gmv": projected_inc_gmv,
            "currency": "INR"
        }

    @classmethod
    def handle_query(
        cls,
        db: Session,
        merchant_id: str,
        message: str,
        trace_id: Optional[str] = None
    ) -> MerchantAgentQueryResponse:
        """
        Handles conversational natural language merchant queries.
        Resolves intent into deterministic opportunity discovery and generates dual views.
        """
        assigned_trace = trace_id or f"trc_merch_agent_{uuid.uuid4().hex[:8]}"
        q_lower = message.lower().strip()

        # Record audit event: Request Received
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=assigned_trace,
            actor_type="USER",
            actor_id="merchant_admin",
            action="MERCHANT_AGENT_REQUEST_RECEIVED",
            event_type="MERCHANT_AGENT_REQUEST_RECEIVED",
            status="SUCCESS",
            metadata_json={"query": message}
        )

        # Intent detection
        filter_types: Optional[List[str]] = None
        intent = "REVENUE_GROWTH"

        if any(w in q_lower for w in ["cross-sell", "cross sell", "complementary", "attach"]):
            filter_types = ["CROSS_SELL"]
            intent = "CROSS_SELL"
        elif any(w in q_lower for w in ["upsell", "up-sell", "upgrade", "premium"]):
            filter_types = ["UPSELL"]
            intent = "UPSELL"
        elif any(w in q_lower for w in ["bundle", "combo", "package"]):
            filter_types = ["BUNDLE"]
            intent = "BUNDLE"
        elif any(w in q_lower for w in ["stock", "inventory", "stockout", "restock"]):
            filter_types = ["INVENTORY_RISK", "INVENTORY_OPPORTUNITY"]
            intent = "INVENTORY_OPPORTUNITY"
        elif any(w in q_lower for w in ["competitor", "pricing", "price alignment", "cheaper"]):
            filter_types = ["PRICE_COMPETITIVENESS"]
            intent = "PRICE_COMPETITIVENESS"

        # Record audit event: Revenue Analysis Started
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=assigned_trace,
            actor_type="AGENT",
            actor_id="MerchantRevenueAgent",
            action="REVENUE_ANALYSIS_STARTED",
            event_type="REVENUE_ANALYSIS_STARTED",
            status="SUCCESS",
            metadata_json={"intent": intent, "filter_types": filter_types}
        )

        # Execute deterministic discovery
        opps = RevenueOpportunityEngine.discover_opportunities(
            db=db,
            merchant_id=merchant_id,
            types=filter_types,
            min_confidence=0.70,
            trace_id=assigned_trace
        )

        # Build responses with Dual Views
        enriched_opp_responses: List[RevenueOpportunityResponse] = []
        for opp in opps:
            hv, av = RevenueOpportunityEngine.format_views(db, opp, merchant_id)
            resp = RevenueOpportunityResponse.model_validate(opp)
            resp.human_view = hv
            resp.agent_view = av
            enriched_opp_responses.append(resp)

        top_hv = enriched_opp_responses[0].human_view if enriched_opp_responses else None
        top_av = enriched_opp_responses[0].agent_view if enriched_opp_responses else None

        if enriched_opp_responses:
            summary = (
                f"I analyzed your catalog, live inventory, and transaction history. "
                f"Discovered {len(enriched_opp_responses)} evidence-backed revenue opportunities for your inquiry. "
                f"Top recommendation: **{enriched_opp_responses[0].title}** with estimated impact: {enriched_opp_responses[0].human_view.financial_impact}."
            )
        else:
            summary = (
                "I analyzed your catalog and sales velocity. No immediate opportunities detected meeting confidence thresholds "
                "or data is currently insufficient for statistical significance."
            )

        return MerchantAgentQueryResponse(
            query=message,
            summary_message=summary,
            intent_detected=intent,
            total_opportunities_found=len(enriched_opp_responses),
            opportunities=enriched_opp_responses,
            top_human_view=top_hv,
            top_agent_view=top_av,
            trace_id=assigned_trace
        )
