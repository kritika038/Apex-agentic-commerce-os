from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.database.models.revenue_opportunity import RevenueOpportunity
from app.database.models.policy import Policy
from app.database.models.product import Product

class RevenueProposalEngine:
    """
    Controlled AI-Assisted Proposal Layer:
    Generates customer-facing campaign messaging, reasoning, and opportunity ranking.
    
    Security Invariant:
    - LLM provides creative copy and proposal rationale.
    - Deterministic backend dictates prices, inventory availability, and policy discount limits.
    """

    @staticmethod
    def format_proposal(db: Session, opportunity: RevenueOpportunity) -> Dict[str, Any]:
        # Fetch active merchant policy for discount ceiling
        policy = db.query(Policy).filter(
            Policy.merchant_id == opportunity.merchant_id,
            Policy.is_active == True
        ).order_by(Policy.version.desc()).first()

        max_allowed_discount = policy.max_discount_percent if policy else Decimal("5.00")

        # Fetch product details
        source_p = db.query(Product).filter(Product.id == opportunity.source_product_id).first() if opportunity.source_product_id else None
        target_products = db.query(Product).filter(Product.id.in_(opportunity.target_product_ids)).all() if opportunity.target_product_ids else []

        products_facts = []
        for p in target_products:
            stock = p.inventory.stock_quantity if p.inventory else 0
            products_facts.append({
                "product_id": p.id,
                "name": p.name,
                "unit_price": str(p.price),
                "stock_available": stock
            })

        return {
            "opportunity_id": opportunity.id,
            "title": opportunity.title,
            "type": opportunity.type,
            "ai_proposal": {
                "headline": f"Unlock Incremental Revenue with {opportunity.title}",
                "customer_message": opportunity.description,
                "reasoning": opportunity.reason,
                "ai_confidence_score": f"{int(opportunity.confidence * 100)}%" if opportunity.confidence is not None else "INSUFFICIENT_DATA"
            },
            "server_authoritative_facts": {
                "source_product": source_p.name if source_p else "General Catalog",
                "target_products": products_facts,
                "proposed_discount": f"{Decimal(str(opportunity.proposed_discount_percent)):.2f}%",
                "policy_max_discount": f"{Decimal(str(max_allowed_discount)):.2f}%",
                "policy_compliant": opportunity.proposed_discount_percent <= max_allowed_discount,
                "authority_source": "SQL_DATABASE_DETERMINISTIC_CORE"
            }
        }
