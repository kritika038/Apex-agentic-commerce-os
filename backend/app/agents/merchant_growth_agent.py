import uuid
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.revenue_opportunity import RevenueOpportunity
from app.database.models.cart import Cart, CartItem
from app.revenue.opportunity_engine import RevenueOpportunityEngine
from app.services.audit_service import AuditService

from app.agents.merchant_revenue_agent import MerchantRevenueAgent

class MerchantGrowthAgent(MerchantRevenueAgent):
    """
    Backwards-compatible wrapper delegating to formalized MerchantRevenueAgent.
    """
    pass

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
        projected_inc_gmv = sum([float(o.estimated_net_value) for o in active_opps], 0.0)

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
    def chat(
        cls,
        db: Session,
        merchant_id: str,
        message: str,
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Conversational Merchant AI Growth Copilot:
        Grounded in deterministic metrics, returns actionable revenue guidance and proposals.
        """
        assigned_trace = trace_id or f"trc_growth_chat_{uuid.uuid4().hex[:8]}"
        q_lower = message.lower().strip()

        # Fetch live database overview
        overview = cls.get_growth_overview(db, merchant_id)
        
        # Ensure opportunities exist in database
        opps = RevenueOpportunityEngine.discover_opportunities(
            db=db,
            merchant_id=merchant_id,
            trace_id=assigned_trace
        )

        response_text = ""
        actionable_proposals: List[Dict[str, Any]] = []

        # Intent 1: Stockout / Inventory Risk
        if any(w in q_lower for w in ["stock", "inventory", "stockout", "restock", "bache"]):
            low_stock = overview["low_stock_items"]
            if low_stock:
                items_str = ", ".join([f"**{i['name']}** ({i['current_stock']} units left)" for i in low_stock[:3]])
                response_text = (
                    f"You have {len(low_stock)} product(s) approaching low inventory: {items_str}. "
                    f"I recommend restocking these items to prevent missed sales."
                )
            else:
                response_text = (
                    f"All {overview['catalog_size']} products in your catalog currently have adequate stock levels. "
                    f"No immediate stockout risks detected."
                )
            # Attach inventory risk opportunities
            inv_opps = [o for o in opps if o.type == "INVENTORY_RISK" and o.status == "GENERATED"]
            for o in inv_opps[:2]:
                actionable_proposals.append({
                    "id": o.id,
                    "type": o.type,
                    "title": o.title,
                    "description": o.description,
                    "net_value": float(o.estimated_net_value),
                    "status": o.status
                })

        # Intent 2: Bundles / Smart Bundles / Cross-sells
        elif any(w in q_lower for w in ["bundle", "cross-sell", "upsell", "package", "combo"]):
            bundle_opps = [o for o in opps if o.type in ["BUNDLE", "CROSS_SELL"] and o.status in ["GENERATED", "APPROVED"]]
            if bundle_opps:
                top_b = bundle_opps[0]
                response_text = (
                    f"Based on historical sales and catalog affinity, your strongest bundle opportunity is **{top_b.title}**. "
                    f"{top_b.description} Estimated net incremental revenue: **₹{float(top_b.estimated_net_value):,.2f}** "
                    f"with {int(top_b.confidence * 100)}% algorithmic confidence."
                )
                for o in bundle_opps[:3]:
                    actionable_proposals.append({
                        "id": o.id,
                        "type": o.type,
                        "title": o.title,
                        "description": o.description,
                        "net_value": float(o.estimated_net_value),
                        "status": o.status
                    })
            else:
                response_text = "I analyzed your catalog and inventory. You have solid standalone products ready for bundle creation."

        # Intent 3: General Revenue / Growth / "How can I increase sales?"
        else:
            active_opps = [o for o in opps if o.status in ["GENERATED", "SIMULATED", "APPROVED"]]
            if active_opps:
                top_opp = active_opps[0]
                response_text = (
                    f"Your store currently has **{overview['total_orders']} orders** recorded with **₹{overview['total_gmv']:,.2f} total GMV** "
                    f"(Average Order Value: ₹{overview['average_order_value']:,.2f}). "
                    f"To increase sales right now, I identified **{len(active_opps)} high-impact opportunities** totaling "
                    f"**₹{overview['projected_incremental_gmv']:,.2f}** in projected incremental GMV. "
                    f"Top recommendation: **{top_opp.title}** ({top_opp.description})."
                )
                for o in active_opps[:3]:
                    actionable_proposals.append({
                        "id": o.id,
                        "type": o.type,
                        "title": o.title,
                        "description": o.description,
                        "net_value": float(o.estimated_net_value),
                        "status": o.status
                    })
            else:
                response_text = (
                    f"Your store is operating at ₹{overview['total_gmv']:,.2f} GMV with {overview['total_orders']} orders. "
                    f"All catalog items are active and in stock."
                )

        # Record Audit Event
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=assigned_trace,
            actor_type="USER" if user_id else "AGENT",
            actor_id=user_id or "merchant_user",
            action="AI_GROWTH_COPILOT_QUERY",
            event_type="AI_GROWTH_COPILOT",
            status="SUCCESS",
            metadata_json={
                "query": message,
                "response_preview": response_text[:200],
                "proposals_count": len(actionable_proposals)
            }
        )

        return {
            "reply": response_text,
            "growth_overview": overview,
            "actionable_proposals": actionable_proposals,
            "trace_id": assigned_trace
        }
