from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.cart import Cart, CartItem

class InventoryAnalyticsService:
    """
    Authoritative Inventory & Velocity Intelligence.
    Computes days of stock remaining and risk assessments without fabricating ML claims.
    """

    @staticmethod
    def get_inventory_health_report(
        db: Session,
        merchant_id: str
    ) -> Dict[str, Any]:
        products = db.query(Product).filter(
            Product.merchant_id == merchant_id,
            Product.is_active == True
        ).all()

        total_catalog = len(products)
        low_stock_threshold = 20
        risk_items: List[Dict[str, Any]] = []
        healthy_count = 0

        # Scan 14-day sales velocity
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff_date = now - timedelta(days=14)

        captured_txs = db.query(PaymentTransaction).filter(
            PaymentTransaction.merchant_id == merchant_id,
            PaymentTransaction.status == "CAPTURED",
            PaymentTransaction.created_at >= cutoff_date
        ).all()

        velocity_map: Dict[str, int] = {}
        for tx in captured_txs:
            if not tx.purchase_intent_id:
                continue
            intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == tx.purchase_intent_id).first()
            if not intent:
                continue
            cart = db.query(Cart).filter(Cart.session_id == intent.session_id).first()
            if cart:
                for item in cart.items:
                    velocity_map[item.product_id] = velocity_map.get(item.product_id, 0) + item.quantity

        for p in products:
            stock = p.inventory.stock_quantity if p.inventory else 0
            sold_14d = velocity_map.get(p.id, 0)
            daily_velocity = round(sold_14d / 14.0, 2)

            if daily_velocity > 0:
                days_remaining = round(stock / daily_velocity, 1)
            elif stock > 0:
                days_remaining = None # Slow moving / infinite at zero velocity
            else:
                days_remaining = 0.0

            if stock == 0:
                risk_level = "HIGH"
                explanation = "Stock exhausted. Urgent replenishment needed."
            elif stock <= 5 or (days_remaining is not None and days_remaining <= 5):
                risk_level = "HIGH"
                explanation = f"Critical inventory: {stock} units left (~{days_remaining or '<5'} days supply at current rate)."
            elif stock < low_stock_threshold or (days_remaining is not None and days_remaining <= 14):
                risk_level = "MEDIUM"
                explanation = f"Low stock alert: {stock} units remaining."
            else:
                risk_level = "LOW"
                explanation = f"Healthy inventory buffer: {stock} units in stock."
                healthy_count += 1

            if risk_level in ["HIGH", "MEDIUM"]:
                risk_items.append({
                    "product_id": p.id,
                    "product_name": p.name,
                    "category": p.category,
                    "price": float(p.price),
                    "current_stock": stock,
                    "daily_velocity": daily_velocity,
                    "units_sold_14d": sold_14d,
                    "estimated_days_remaining": days_remaining if days_remaining is not None else "INSUFFICIENT_VELOCITY_DATA",
                    "risk_level": risk_level,
                    "explanation": explanation
                })

        return {
            "total_products": total_catalog,
            "healthy_stock_count": healthy_count,
            "risk_alerts_count": len(risk_items),
            "high_risk_count": sum(1 for r in risk_items if r["risk_level"] == "HIGH"),
            "risk_items": risk_items,
            "calculated_at": now.isoformat()
        }
