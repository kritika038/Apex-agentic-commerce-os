"""
Authoritative AI Buyer Agent.
Orchestrates natural language intent parsing, controlled tool usage, deterministic hard filtering,
governed purchase intent creation, and customer-authorized checkout preparation.
"""

import re
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.database.models.base import generate_uuid
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.database.models.shopping_session import ShoppingSession
from app.agents.intent_engine import ConversationIntentEngine
from app.tools.buyer_tools import (
    tool_search_products,
    tool_get_product,
    tool_check_inventory,
    tool_compare_prices,
    tool_create_purchase_intent,
    tool_get_purchase_intent,
    tool_get_checkout_state
)
from app.services.audit_service import AuditService
from app.services.agent_tracing_service import AgentTracingService
from app.schemas.agent_catalog import (
    AgentProductDetail,
    AgentBuyerActResponse,
    AgentPurchaseIntentDetail
)

class BuyerAgent:
    def __init__(
        self,
        db: Session,
        user: Optional[User] = None,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        merchant_id: Optional[str] = None
    ):
        self.db = db
        self.user = user
        self.session_id = session_id or f"sess_buyer_{generate_uuid()[:12]}"
        self.trace_id = trace_id or f"trc_buyer_{generate_uuid()[:12]}"
        self.merchant_id = merchant_id
        self.agent_id = "apex_buyer_agent_v2"
        self.agent_version = "2.0.0"

    def _get_or_create_session(self) -> ShoppingSession:
        merchant = self._resolve_merchant()
        sess = self.db.query(ShoppingSession).filter(
            ShoppingSession.id == self.session_id,
            ShoppingSession.merchant_id == merchant.id
        ).first()
        if not sess:
            sess = ShoppingSession(
                id=self.session_id,
                merchant_id=merchant.id,
                customer_identifier=self.user.email if self.user else "anonymous_shopper",
                context_data={}
            )
            self.db.add(sess)
            self.db.commit()
            self.db.refresh(sess)
        return sess

    def _resolve_merchant(self) -> Merchant:
        if self.merchant_id:
            m = self.db.query(Merchant).filter(Merchant.id == self.merchant_id).first()
            if m:
                return m
        m = self.db.query(Merchant).filter(Merchant.is_active == True).first()
        if not m:
            m = Merchant(id=f"mer_{generate_uuid()[:12]}", name="Apex Sports", is_active=True)
            self.db.add(m)
            self.db.commit()
            self.db.refresh(m)
        return m

    def act(
        self,
        message: str,
        delivery_address: Optional[Dict[str, Any]] = None,
        coupon_code: Optional[str] = None,
        use_coins: bool = False
    ) -> AgentBuyerActResponse:
        merchant = self._resolve_merchant()
        session_obj = self._get_or_create_session()
        raw_ctx = session_obj.context_data or {}
        context_data = dict(raw_ctx)
        active_intent = context_data.get("active_intent", {})
        previous_products = context_data.get("previous_products", [])

        # 1. Audit Inbound Request & Start Agent Trace
        AuditService.record_event(
            db=self.db,
            merchant_id=merchant.id,
            trace_id=self.trace_id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            actor_type="USER" if self.user else "ANONYMOUS_BUYER",
            action="BUYER_REQUEST_RECEIVED",
            event_type="BUYER_AGENT_REQUEST",
            status="SUCCESS",
            metadata_json={"message": message[:250]}
        )

        agent_trace = AgentTracingService.start_agent_trace(
            db=self.db,
            trace_id=self.trace_id,
            merchant_id=merchant.id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            agent_type="BUYER_AGENT",
            agent_version=self.agent_version,
            input_data={"message": message}
        )

        tool_calls: List[Dict[str, Any]] = []

        # 2. Structured Intent Analysis via ConversationIntentEngine + Entity Matcher
        analysis = ConversationIntentEngine.analyze_message(
            message=message,
            active_intent=active_intent,
            previous_products=previous_products,
            cart=None,
            user_profile={"email": self.user.email if self.user else None}
        )

        action = analysis.get("action", "SEARCH")
        extracted_intent = analysis.get("search_params", {})
        budget_max = extracted_intent.get("max_price") or active_intent.get("budget_max")
        category = extracted_intent.get("category") or active_intent.get("category")
        brand = extracted_intent.get("brand") or active_intent.get("brand")
        color = extracted_intent.get("color") or active_intent.get("color")
        size = extracted_intent.get("size") or active_intent.get("size")
        quantity = extracted_intent.get("quantity", 1)

        # Explicit entity extractions from natural message
        msg_lower = message.lower()
        for c in ["classic black", "pure white", "navy blue", "crimson red", "black", "white", "navy", "red", "blue", "grey", "gray", "green"]:
            if re.search(r'\b' + re.escape(c) + r'\b', msg_lower):
                color = c
                break

        for s in ["extra large", "xxl", "xl", "large", "medium", "small", "uk 6", "uk 7", "uk 8", "uk 9", "uk 10", "uk 11"]:
            if re.search(r'\b' + re.escape(s) + r'\b', msg_lower):
                size = s
                break

        for b in ["Nike", "Adidas", "Puma", "Reebok", "Asics", "Under Armour", "Apex"]:
            if re.search(r'\b' + re.escape(b) + r'\b', message, re.IGNORECASE):
                brand = b
                break

        qty_match = re.search(r'\b(?:buy|order|get|need|want)\s+(\d+)\b', message, re.IGNORECASE)
        if qty_match:
            try:
                quantity = int(qty_match.group(1))
            except Exception:
                pass

        if "one " in msg_lower or msg_lower.endswith(" one") or "single " in msg_lower:
            if not qty_match:
                quantity = 1

        # Check for bottle category
        if "bottle" in msg_lower:
            category = "Water Bottle"

        # Check for direct product name mentions
        named_product_match = None
        for p_name in ["Pro Running Shoes", "SpeedFlow Marathon Shoes", "Air Cushion Trail Running Shoes", "Sports Dry-Fit T-Shirt", "Insulated Steel Water Bottle", "Running Shorts", "Performance Socks"]:
            if p_name.lower() in msg_lower:
                named_product_match = p_name
                break

        # Update Session Intent Memory
        active_intent.update({
            "category": category,
            "budget_max": budget_max,
            "brand": brand,
            "color": color,
            "size": size,
            "quantity": quantity,
            "product_name": named_product_match
        })
        context_data["active_intent"] = active_intent

        AuditService.record_event(
            db=self.db,
            merchant_id=merchant.id,
            trace_id=self.trace_id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            actor_type="AGENT",
            action="INTENT_RESOLVED",
            event_type="INTENT_RESOLUTION",
            status="SUCCESS",
            metadata_json=active_intent
        )

        candidate_products: List[AgentProductDetail] = []
        selected_product: Optional[AgentProductDetail] = None
        purchase_intent_detail: Optional[AgentPurchaseIntentDetail] = None
        order_review_dict: Optional[Dict[str, Any]] = None
        governance_dict: Optional[Dict[str, Any]] = None
        next_action = "DISCOVERY"
        reply_message = ""

        is_buy_command = "BUY" in action or any(
            re.search(r'\b' + re.escape(w) + r'\b', msg_lower)
            for w in ["buy", "purchase", "order", "checkout", "take it", "get it"]
        )

        # 3. Action Execution Flow
        if is_buy_command:
            if quantity > 5:
                reply_message = f"Purchase blocked by governance policy (Requested quantity {quantity} exceeds maximum limit of 5 items per transaction)."
                next_action = "BLOCKED"
                governance_dict = {
                    "decision": "DENY",
                    "requires_human_approval": False,
                    "threshold_evaluated": "Max Quantity 5",
                    "status": "DENY"
                }
            elif not self.user:
                reply_message = "Authentication required: Please sign in as a customer before authorizing a purchase."
                next_action = "BLOCKED"
            else:
                # Resolve target product from candidate/previous selection
                target_p_dict = context_data.get("selected_product") or (previous_products[0] if previous_products else None)
                if not target_p_dict:
                    search_res = tool_search_products(
                        db=self.db,
                        merchant_id=merchant.id,
                        category=category,
                        budget_max=budget_max,
                        brand=brand,
                        color=color,
                        size=size,
                        in_stock_only=True
                    )
                    tool_calls.append({"tool": "search_products", "arguments": {"category": category, "budget_max": budget_max}, "result_count": search_res["count"]})
                    if search_res["results"]:
                        target_p_dict = search_res["results"][0]

                if target_p_dict:
                    prod_id = target_p_dict.get("product_id") or target_p_dict.get("id")
                    inv_res = tool_check_inventory(db=self.db, product_id=prod_id, requested_quantity=quantity)
                    tool_calls.append({"tool": "check_inventory", "arguments": {"product_id": prod_id, "quantity": quantity}, "available": inv_res["available"]})

                    if not inv_res["available"]:
                        reply_message = f"Selected product **{target_p_dict.get('name')}** is currently out of stock."
                        next_action = "BLOCKED"
                    else:
                        # Create immutable purchase intent
                        pi_res = tool_create_purchase_intent(
                            db=self.db,
                            product_id=prod_id,
                            buyer_id=self.user.id,
                            merchant_id=merchant.id,
                            session_id=self.session_id,
                            variant_id=target_p_dict.get("variant_id") or f"{color or 'Standard'}-{size or 'Standard'}",
                            quantity=quantity,
                            delivery_address=delivery_address or context_data.get("delivery_address"),
                            coupon_code=coupon_code,
                            use_coins=use_coins,
                            trace_id=self.trace_id
                        )
                        tool_calls.append({"tool": "create_purchase_intent", "arguments": {"product_id": prod_id, "quantity": quantity}, "status": pi_res.get("status")})

                        if pi_res["success"]:
                            pi_id = pi_res["purchase_intent_id"]
                            gov_dec = pi_res["governance_decision"]
                            req_app = pi_res["requires_human_approval"]

                            governance_dict = {
                                "decision": gov_dec,
                                "requires_human_approval": req_app,
                                "threshold_evaluated": "₹5,000 Autonomous / ₹10,000 Policy Max",
                                "status": "PASS" if gov_dec == "ALLOW" else gov_dec
                            }

                            order_review_dict = pi_res["order_review"]
                            purchase_intent_detail = AgentPurchaseIntentDetail(
                                purchase_intent_id=pi_id,
                                status=pi_res["status"],
                                buyer_id=self.user.id,
                                merchant_id=merchant.id,
                                product_id=prod_id,
                                product_name=pi_res["product_name"],
                                variant_id=pi_res.get("variant_id"),
                                quantity=quantity,
                                authoritative_unit_price=pi_res["unit_price"],
                                total_amount=pi_res["total_amount"],
                                discount_amount=pi_res.get("discount_amount", 0.0),
                                currency="INR",
                                governance_decision=gov_dec,
                                requires_human_approval=req_app,
                                trace_id=self.trace_id,
                                created_at=session_obj.created_at.isoformat() if session_obj.created_at else "",
                                order_review=order_review_dict,
                                message="Order review prepared. Explicit customer authorization required for payment."
                            )

                            if gov_dec == "DENY":
                                reply_message = f"Purchase blocked by governance policy (Transaction total exceeds policy threshold limit)."
                                next_action = "BLOCKED"
                            elif req_app:
                                reply_message = f"Order review prepared for **{pi_res['product_name']}** (₹{pi_res['total_amount']:,.2f}). Human merchant approval required before checkout."
                                next_action = "CONFIRMATION"
                            else:
                                reply_message = f"Order review prepared for **{pi_res['product_name']}** (₹{pi_res['total_amount']:,.2f}). Please review and click [Confirm & Pay] to authorize test payment via Razorpay."
                                next_action = "PAYMENT_READY"
                else:
                    reply_message = "No matching product available to buy. Please specify what you'd like to find."
                    next_action = "DISCOVERY"

        else:
            # Search & Recommendation Path with Hard Filters First
            search_res = tool_search_products(
                db=self.db,
                merchant_id=merchant.id,
                query=named_product_match,
                category=category,
                budget_max=budget_max,
                brand=brand,
                color=color,
                size=size,
                in_stock_only=True
            )
            tool_calls.append({"tool": "search_products", "arguments": {"category": category, "budget_max": budget_max, "brand": brand}, "count": search_res["count"]})

            raw_results = search_res["results"]
            candidate_products = [AgentProductDetail(**r) for r in raw_results]

            # Price comparison tool call if requested
            if any(w in msg_lower for w in ["compare", "cheaper", "verified price", "other stores"]) and candidate_products:
                top_p = candidate_products[0]
                comp_res = tool_compare_prices(db=self.db, product_id=top_p.product_id)
                tool_calls.append({"tool": "compare_prices", "arguments": {"product_id": top_p.product_id}, "result": comp_res})

            if candidate_products:
                selected_product = candidate_products[0]
                context_data["selected_product"] = selected_product.model_dump()
                context_data["previous_products"] = [p.model_dump() for p in candidate_products]

                # Factual explanation derived from structured constraints
                reasons = []
                if budget_max:
                    reasons.append(f"within your ₹{int(budget_max):,} budget (₹{selected_product.price:,.2f})")
                if brand:
                    reasons.append(f"matches your {brand} preference")
                if color:
                    reasons.append(f"in {color}")
                if selected_product.inventory_available:
                    reasons.append("verified in stock")

                reason_str = ", ".join(reasons) if reasons else f"priced at ₹{selected_product.price:,.2f}"
                reply_message = f"I found **{selected_product.name}** by {selected_product.brand} — {reason_str}. Say **'Buy this'** to prepare your order."
                next_action = "SELECTION"
            else:
                reply_message = f"I could not find any in-stock items matching your criteria ({category or 'products'}"
                if budget_max:
                    reply_message += f" under ₹{int(budget_max):,}"
                if brand:
                    reply_message += f" by {brand}"
                reply_message += "). Try adjusting your budget or search terms."
                next_action = "DISCOVERY"

        # 4. Save Session State
        session_obj.context_data = context_data
        self.db.commit()

        # 5. Build Structured Agent View Payload
        agent_view = {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "intent": active_intent,
            "hard_constraints": {
                "category": category,
                "budget_max": budget_max,
                "brand": brand,
                "color": color,
                "size": size,
                "quantity": quantity
            },
            "candidate_count": len(candidate_products),
            "selected_product_id": selected_product.product_id if selected_product else None,
            "purchase_intent_id": purchase_intent_detail.purchase_intent_id if purchase_intent_detail else None,
            "governance_status": governance_dict.get("status") if governance_dict else "EVALUATED_AT_PURCHASE",
            "next_action": next_action
        }

        return AgentBuyerActResponse(
            session_id=self.session_id,
            trace_id=self.trace_id,
            reply_message=reply_message,
            intent=active_intent,
            tool_calls=tool_calls,
            candidate_products=candidate_products,
            selected_product=selected_product,
            purchase_intent=purchase_intent_detail,
            order_review=order_review_dict,
            governance=governance_dict,
            next_action=next_action,
            agent_view=agent_view
        )
