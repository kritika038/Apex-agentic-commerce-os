from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from decimal import Decimal

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.services.audit_service import AuditService

class DynamicPricingService:
    """
    Advisory Dynamic Pricing Intelligence.
    Produces price recommendations governed by merchant guardrails.
    Requires explicit merchant approval to mutate catalog state.
    """

    @staticmethod
    def get_pricing_recommendations(
        db: Session,
        merchant_id: str
    ) -> List[Dict[str, Any]]:
        products = db.query(Product).filter(
            Product.merchant_id == merchant_id,
            Product.is_active == True
        ).all()

        proposals = []
        for p in products:
            stock = p.inventory.stock_quantity if p.inventory else 10
            cur_price = Decimal(str(p.price))

            # Strategy: If high stock (>30) and slow velocity, propose small 5-8% promotional price reduction
            if stock >= 25:
                discount_pct = Decimal("6.0")
                suggested_price = (cur_price * (Decimal("1.00") - (discount_pct / Decimal("100.00")))).quantize(Decimal("1.00"))
                min_allowed_price = cur_price * Decimal("0.80") # 20% max discount guardrail

                if suggested_price >= min_allowed_price:
                    proposals.append({
                        "product_id": str(p.id),
                        "product_name": p.name,
                        "category": p.category,
                        "current_price": float(cur_price),
                        "recommended_price": float(suggested_price),
                        "discount_percent": float(discount_pct),
                        "reason": f"High inventory level ({stock} units). A {discount_pct}% price optimization is projected to accelerate inventory turnover.",
                        "guardrail_compliant": True,
                        "min_price_floor": float(min_allowed_price)
                    })

        return proposals

    @staticmethod
    def apply_approved_price_change(
        db: Session,
        merchant_id: str,
        product_id: str,
        new_price: Decimal,
        approved_by_user_id: str,
        reason: str
    ) -> Product:
        prod = db.query(Product).filter(
            Product.id == product_id,
            Product.merchant_id == merchant_id
        ).first()

        if not prod:
            raise ValueError(f"Product {product_id} not found.")

        old_price = prod.price
        prod.price = new_price
        db.commit()
        db.refresh(prod)

        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            event_type="DYNAMIC_PRICE_UPDATED",
            entity_type="Product",
            entity_id=prod.id,
            actor_type="MERCHANT",
            actor_id=approved_by_user_id,
            payload_snapshot={
                "old_price": str(old_price),
                "new_price": str(new_price),
                "reason": reason
            }
        )

        return prod
