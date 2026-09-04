import json
import time
import re
from typing import List, Dict, Any, Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from app.ai.gateway import LLMGateway
from app.schemas.ai import ChatMessage, ChatResponse, OrderReview, OrderReviewItem
from app.tools.registry import tool_registry
from app.database.models.base import generate_uuid
from app.database.models.agent import Agent
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart, CartItem
from app.database.models.user import User
from app.database.models.shopping_session import ShoppingSession
from app.services.audit_service import AuditService
from app.services.agent_tracing_service import AgentTracingService
from app.services.pricing_service import PricingService
from app.agents.intent_engine import ConversationIntentEngine
from app.tools.shopping_tools import search_products, add_to_cart, get_cart

class ShoppingAgent:
    def __init__(
        self,
        db: Session,
        merchant_id: str,
        session_id: str,
        gateway: Optional[LLMGateway] = None,
        trace_id: Optional[str] = None,
        user: Optional[User] = None,
        delivery_address: Optional[Dict[str, Any]] = None,
        applied_coupon: Optional[str] = None,
        applied_voucher: Optional[str] = None,
        use_coins: bool = False
    ):
        self.db = db
        self.merchant_id = merchant_id
        self.session_id = session_id
        self.gateway = gateway or LLMGateway()
        self.trace_id = trace_id or f"trc_{generate_uuid()[:12]}"
        self.user = user
        self.delivery_address = delivery_address
        self.applied_coupon = applied_coupon
        self.applied_voucher = applied_voucher
        self.use_coins = use_coins
        
        self.permissions = ["READ_PRODUCTS", "READ_INVENTORY", "CREATE_CART", "READ_CART", "MODIFY_CART", "CALCULATE_CART"]
        self.agent_id = "shopping_agent_v1"
        self.agent_version = "1.0.0"

    def _get_or_create_session(self) -> ShoppingSession:
        session = self.db.query(ShoppingSession).filter(
            ShoppingSession.id == self.session_id,
            ShoppingSession.merchant_id == self.merchant_id
        ).first()

        if not session:
            session = ShoppingSession(
                id=self.session_id,
                merchant_id=self.merchant_id,
                customer_identifier=self.user.email if self.user else "customer",
                context_data={}
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            
        return session

    def _execute_tool(self, name: str, arguments: Dict[str, Any], agent_trace_id: Optional[str] = None, step_seq: int = 1) -> str:
        start_time = time.time()
        perm_err = tool_registry.verify_permission(
            tool_name=name,
            agent_permissions=self.permissions,
            agent_name="ShoppingAgent"
        )
        
        if perm_err:
            dur = (time.time() - start_time) * 1000.0
            if agent_trace_id:
                AgentTracingService.record_step(
                    db=self.db,
                    trace_id=self.trace_id,
                    agent_trace_id=agent_trace_id,
                    sequence_number=step_seq,
                    step_type="TOOL_CALL",
                    tool_name=name,
                    input_data=arguments,
                    output_data=perm_err,
                    decision="PERMISSION_DENIED",
                    duration_ms=dur,
                    status="DENIED",
                    error_code="PERMISSION_DENIED"
                )
            AuditService.record_event(
                db=self.db,
                merchant_id=self.merchant_id,
                trace_id=self.trace_id,
                session_id=self.session_id,
                agent_id=self.agent_id,
                agent_version=self.agent_version,
                actor_type="AGENT",
                action=name,
                event_type="TOOL_EXECUTION",
                tool_name=name,
                status="DENIED",
                error_code="PERMISSION_DENIED",
                reason=perm_err.get("error", "Permission Denied"),
                metadata_json={"arguments": arguments, "error": perm_err}
            )
            return json.dumps(perm_err)
            
        func = tool_registry.get_tool(name)
        try:
            result = func(db=self.db, merchant_id=self.merchant_id, session_id=self.session_id, **arguments)
            dur = (time.time() - start_time) * 1000.0
            
            if agent_trace_id:
                AgentTracingService.record_step(
                    db=self.db,
                    trace_id=self.trace_id,
                    agent_trace_id=agent_trace_id,
                    sequence_number=step_seq,
                    step_type="TOOL_CALL",
                    tool_name=name,
                    input_data=arguments,
                    output_data=result,
                    decision="EXECUTED",
                    duration_ms=dur,
                    status="SUCCESS"
                )
            AuditService.record_event(
                db=self.db,
                merchant_id=self.merchant_id,
                trace_id=self.trace_id,
                session_id=self.session_id,
                agent_id=self.agent_id,
                agent_version=self.agent_version,
                actor_type="AGENT",
                action=name,
                event_type="TOOL_EXECUTION",
                tool_name=name,
                status="SUCCESS",
                metadata_json={"arguments": arguments, "result_preview": str(result)[:300]}
            )
            return json.dumps(result)
        except Exception as e:
            dur = (time.time() - start_time) * 1000.0
            err_dict = {"error": f"Tool execution failed: {str(e)}"}
            if agent_trace_id:
                AgentTracingService.record_step(
                    db=self.db,
                    trace_id=self.trace_id,
                    agent_trace_id=agent_trace_id,
                    sequence_number=step_seq,
                    step_type="TOOL_CALL",
                    tool_name=name,
                    input_data=arguments,
                    output_data=err_dict,
                    decision="FAILED",
                    duration_ms=dur,
                    status="FAILED",
                    error_code="EXECUTION_ERROR"
                )
            AuditService.record_event(
                db=self.db,
                merchant_id=self.merchant_id,
                trace_id=self.trace_id,
                session_id=self.session_id,
                agent_id=self.agent_id,
                agent_version=self.agent_version,
                actor_type="AGENT",
                action=name,
                event_type="TOOL_EXECUTION",
                tool_name=name,
                status="FAILED",
                error_code="TOOL_EXECUTION_FAILED",
                reason=str(e),
                metadata_json={"arguments": arguments}
            )
            return json.dumps(err_dict)

    def process_message(self, message: str) -> ChatResponse:
        # 1. Audit Inbound AI Request & Start Agent Trace
        AuditService.record_event(
            db=self.db,
            merchant_id=self.merchant_id,
            trace_id=self.trace_id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            actor_type="USER",
            action="AI_REQUEST",
            event_type="AI_REQUEST",
            status="SUCCESS",
            metadata_json={"message_preview": message[:200]}
        )

        agent_trace = AgentTracingService.start_agent_trace(
            db=self.db,
            trace_id=self.trace_id,
            merchant_id=self.merchant_id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            agent_type="SHOPPING_AGENT",
            agent_version=self.agent_version,
            input_data={"message": message}
        )

        # 2. Retrieve session context data
        session = self._get_or_create_session()
        raw_ctx = session.context_data or {}
        context_data = dict(raw_ctx)
        active_intent = context_data.get("active_intent", {})
        previous_products = context_data.get("previous_products", [])
        history = context_data.get("history", [])

        # Read or update delivery address in context
        if self.delivery_address:
            context_data["delivery_address"] = self.delivery_address

        current_cart_state = get_cart(db=self.db, merchant_id=self.merchant_id, session_id=self.session_id)

        tool_call_count = 0
        step_seq = 1

        # 3. Analyze intent with ConversationIntentEngine
        analysis = ConversationIntentEngine.analyze_message(
            message=message,
            active_intent=active_intent,
            previous_products=previous_products,
            cart=current_cart_state,
            user_profile={"email": self.user.email if self.user else None}
        )

        action = analysis.get("action")
        lang = analysis.get("language", "english")
        is_hi = lang in ["hindi", "hinglish"]

        final_message = ""
        discovered_products: List[Dict[str, Any]] = []
        response_actions: List[str] = []
        structured_intent: Optional[Dict[str, Any]] = None
        order_review_obj: Optional[OrderReview] = None
        requires_approval = False
        approval_details: Optional[Dict[str, Any]] = None

        if action == "RESET":
            context_data["active_intent"] = {"language": lang}
            context_data["previous_products"] = []
            final_message = analysis["message"]
            discovered_products = []
            structured_intent = {
                "query": "",
                "category": None,
                "max_price": None,
                "min_price": None,
                "quantity": 1,
                "sort": None,
                "in_stock_only": False,
                "clarification_needed": False
            }

        elif action == "CLARIFICATION_NEEDED":
            final_message = analysis["message"]
            discovered_products = []
            structured_intent = analysis.get("structured_intent") or {
                "query": message,
                "category": active_intent.get("category"),
                "max_price": None,
                "min_price": None,
                "quantity": 1,
                "sort": None,
                "in_stock_only": False,
                "clarification_needed": True
            }

        elif action in ["BEST_PRODUCT_DIRECT", "CHEAPEST_PRODUCT_DIRECT", "COMPARISON_DIRECT"]:
            final_message = analysis["message"]
            discovered_products = analysis.get("products", [])
            if discovered_products:
                context_data["selected_product"] = discovered_products[0]
                context_data["selected_product_id"] = discovered_products[0].get("id")
                context_data["candidate_product_ids"] = [p.get("id") for p in previous_products if p.get("id")]
                context_data["previous_products"] = discovered_products
            structured_intent = {
                "query": active_intent.get("category", "Products"),
                "category": active_intent.get("category"),
                "max_price": active_intent.get("budget_max"),
                "min_price": None,
                "quantity": 1,
                "sort": "best" if "BEST" in action else ("price_asc" if "CHEAPEST" in action else None),
                "in_stock_only": True,
                "clarification_needed": False
            }

        elif action == "VIEW_CART":
            final_message = analysis.get("message", "Here is your current cart:")
            discovered_products = []

        elif action == "CHECK_COUPONS":
            final_message = analysis.get("message", "We have active promo code **SAVE500** available for orders above ₹5,000.")
            discovered_products = []

        elif action == "CANCEL_INQUIRY":
            final_message = analysis.get("message", "You can cancel your order directly from /orders if it is in PROCESSING or CONFIRMED status.")
            discovered_products = []

        elif action == "CHECK_REWARDS":
            if self.user:
                from app.services.reward_service import RewardService
                summary = RewardService.get_customer_rewards_summary(self.db, self.user, self.merchant_id)
                coins_val = summary.coins_balance / 10
                final_message = (
                    f"Aapke account mein **{summary.coins_balance} Apex Coins** (worth ₹{coins_val:,.2f} instant discount) aur **{summary.points_balance} Loyalty Points** ({summary.tier} Tier) available hain. Aap inhe checkout par apply kar sakte hain."
                    if is_hi else
                    f"You currently have **{summary.coins_balance} Apex Coins** (worth ₹{coins_val:,.2f} discount) and **{summary.points_balance} Loyalty Points** ({summary.tier} Tier). You can redeem them directly at checkout."
                )
            else:
                final_message = (
                    "Sign in karke aap Welcome 500 Apex Coins earn kar sakte hain aur har purchase par extra coins kama sakte hain."
                    if is_hi else
                    "Sign in to earn 500 Welcome Apex Coins and redeem points on every purchase."
                )
            discovered_products = []

        elif action == "CHECK_ORDERS":
            buyer_id = self.user.email if self.user else None
            if buyer_id:
                from app.services.order_service import OrderService
                user_orders = OrderService.get_customer_orders(self.db, buyer_id=buyer_id, limit=3)
                if user_orders:
                    latest = user_orders[0]
                    items_str = ", ".join([f"{it.name} (Qty: {it.quantity})" for it in latest.items])
                    final_message = (
                        f"Aapki pichli order **#{latest.order_number}** ({latest.status}) thi jisme **{items_str}** shamil the (Total: ₹{latest.total_amount:,.0f}). Aap /orders page par sabhi orders dekh sakte hain."
                        if is_hi else
                        f"Your most recent verified order was **#{latest.order_number}** ({latest.status}) containing **{items_str}** for ₹{latest.total_amount:,.0f}. You can view full tracking at /orders/{latest.id}."
                    )
                else:
                    final_message = (
                        "Aapki abhi tak koi verified previous order nahi hai. Aap hamare catalog se products search karke direct order kar sakte hain."
                        if is_hi else
                        "You don't have any previous orders yet. Feel free to search and explore verified products in our catalog."
                    )
            else:
                final_message = (
                    "Apni previous orders dekhne ke liye please account mein Sign In karein."
                    if is_hi else
                    "Please sign in to view your previous verified orders."
                )
            discovered_products = []

        elif action == "ORDER_STATUS":
            buyer_id = self.user.email if self.user else None
            if buyer_id:
                from app.services.order_service import OrderService
                user_orders = OrderService.get_customer_orders(self.db, buyer_id=buyer_id, limit=1)
                if user_orders:
                    latest = user_orders[0]
                    final_message = (
                        f"Aapka latest order **#{latest.order_number}** ({latest.status}) processing mein hai. Payment **{latest.payment.status}** ho chuki hai aur delivery standard 2-3 dino mein expected hai. Full status: /orders/{latest.id}"
                        if is_hi else
                        f"Your latest order **#{latest.order_number}** is **{latest.status}** with payment **{latest.payment.status}**. Track live progress at /orders/{latest.id}."
                    )
                else:
                    final_message = "Aapka koi active shipment nahi mila." if is_hi else "No active order found to track."
            else:
                final_message = "Live tracking dekhne ke liye please Sign In karein." if is_hi else "Please sign in to track your order."
            discovered_products = []

        elif action == "REORDER_PREVIOUS":
            buyer_id = self.user.email if self.user else None
            if buyer_id:
                from app.services.order_service import OrderService
                user_orders = OrderService.get_customer_orders(self.db, buyer_id=buyer_id, limit=1)
                if user_orders and user_orders[0].items:
                    latest_item = user_orders[0].items[0]
                    # Reorder items
                    buy_res = OrderService.buy_again(self.db, user_orders[0].id, self.session_id, buyer_id=buyer_id)
                    final_message = (
                        f"Aapki pichli order se **{latest_item.name}** aapke cart mein add kar diya gaya hai (Current Price: ₹{latest_item.unit_price:,.0f}). Checkout ke liye 'checkout my cart' kahein."
                        if is_hi else
                        f"Reordered **{latest_item.name}** from your previous order into your cart at current catalog price. Say 'checkout my cart' to proceed."
                    )
                    response_actions.append("CART_UPDATED")
                else:
                    final_message = "Aapki pichli koi order nahi mili jise dubara order kiya ja sake." if is_hi else "No previous order found to reorder."
            else:
                final_message = "Dubara order karne ke liye please Sign In karein." if is_hi else "Please sign in to reorder items from your order history."
            discovered_products = []

        elif action in ["EXTERNAL_PRICE_CHECK", "COMPARE_PRICES"]:
            from app.services.price_intelligence.canonical_service import CanonicalPriceIntelligenceService
            
            target_prod = analysis.get("target_product") or context_data.get("selected_product")
            p_id = target_prod.get("id") if target_prod else analysis.get("product_id")
            
            if not p_id and previous_products:
                p_id = previous_products[0].get("id")
                target_prod = previous_products[0]

            if not p_id:
                first_p = self.db.query(Product).filter(Product.merchant_id == self.merchant_id, Product.is_active == True).first()
                if first_p:
                    p_id = str(first_p.id)
                    target_prod = {"id": p_id, "name": first_p.name, "price": float(first_p.price)}

            if p_id:
                cmp_res = CanonicalPriceIntelligenceService.get_canonical_comparison(self.db, product_id=p_id)
                canon_p = cmp_res.get("canonical_product", {})
                p_name = canon_p.get("title") or (target_prod.get("name") if target_prod else "Product")
                apex_p = cmp_res.get("apex_price", float(target_prod.get("price", 0)) if target_prod else 0)
                offers = cmp_res.get("offers", [])
                sources_cnt = len(offers) + 1

                offer_lines = [f"• **Apex Store**: ₹{int(apex_p):,} *(Authoritative Direct Checkout)*"]
                for o in offers:
                    store_n = o.get("store_name") or o.get("store_domain")
                    p_val = o.get("price")
                    m_type = o.get("match_type")
                    if p_val is not None:
                        offer_lines.append(f"• **{store_n}**: ₹{int(p_val):,} *(Verified Exact)*")
                    elif m_type == "SEARCH_FALLBACK":
                        offer_lines.append(f"• **{store_n}**: Exact listing unverified *(Search Available)*")
                    else:
                        offer_lines.append(f"• **{store_n}**: Price varies")

                offers_block = "\n".join(offer_lines)

                final_message = (
                    f"Verified Price Intelligence & Price Comparison for **{p_name}** ({sources_cnt} sources checked):\n\n"
                    f"{offers_block}\n\n"
                    f"✓ Apex Store offers immediate authoritative dispatch and Razorpay protection.\n\n"
                    f"*Note: External prices are verified via official manufacturer data where available. Exact Amazon/Flipkart listings remain transparent search queries.*"
                    if not is_hi else
                    f"**{p_name}** ka verified price comparison ({sources_cnt} sources checked):\n\n"
                    f"{offers_block}\n\n"
                    f"✓ Apex Store par verified authoritative checkout available hai.\n\n"
                    f"*Note: Official manufacturer verified prices displayed. Unverified marketplace listings search fallback mein provide ki gayi hain.*"
                )
                
                prod_obj = self.db.query(Product).filter(Product.id == p_id).first()
                if prod_obj:
                    discovered_products = [{
                        "id": str(prod_obj.id),
                        "name": prod_obj.name,
                        "brand": prod_obj.brand,
                        "category": prod_obj.category,
                        "price": float(prod_obj.price),
                        "mrp": float(prod_obj.mrp) if prod_obj.mrp else None,
                        "image_url": prod_obj.image_url or (prod_obj.attributes.get("image_url") if isinstance(prod_obj.attributes, dict) else None),
                        "rating": float(prod_obj.rating) if prod_obj.rating else 4.5,
                        "review_count": prod_obj.review_count or 0,
                        "in_stock": True,
                        "stock_quantity": prod_obj.inventory.stock_quantity if prod_obj.inventory else 10,
                        "external_offers": offers
                    }]
                response_actions.append("PRICE_COMPARISON_VIEWED")
            else:
                final_message = (
                    "Kripya pehle kisi product ko select ya search karein jiska price compare karna hai."
                    if is_hi else
                    "Please search for or select a product to compare prices across verified stores."
                )
                discovered_products = []

        elif action == "FILTER_COLOUR":
            from app.services.shopping_agent.deterministic_ranking import DeterministicRankingEngine
            target_col = analysis.get("colour", "Black")
            
            all_db_prods = self.db.query(Product).filter(Product.merchant_id == self.merchant_id, Product.is_active == True).all()
            prods_dicts = []
            for p in all_db_prods:
                prods_dicts.append({
                    "id": str(p.id),
                    "name": p.name,
                    "brand": p.brand,
                    "category": p.category,
                    "subcategory": p.subcategory,
                    "price": float(p.price),
                    "mrp": float(p.mrp) if p.mrp else None,
                    "image_url": p.image_url,
                    "description": p.description,
                    "tags": p.tags or [],
                    "attributes": p.attributes or {},
                    "stock": p.inventory.stock_quantity if p.inventory else 10,
                    "rating": float(p.rating) if p.rating else 4.5,
                    "review_count": p.review_count or 0
                })

            curr_cat = active_intent.get("category")
            b_max = active_intent.get("budget_max")
            ranked = DeterministicRankingEngine.filter_and_rank(
                products=prods_dicts,
                category=curr_cat,
                budget_max=b_max,
                colour_preference=target_col
            )

            if ranked:
                discovered_products = ranked[:4]
                context_data["previous_products"] = discovered_products
                context_data["selected_product"] = discovered_products[0]
                if "active_intent" not in context_data:
                    context_data["active_intent"] = {}
                context_data["active_intent"]["colour_preference"] = target_col
                top_p = discovered_products[0]
                final_message = (
                    f"Maine **{target_col}** options filter kar diye hain:\n\n"
                    f"✓ Top match: **{top_p['name']}** (₹{int(top_p['price']):,})\n\n"
                    f"Isko order karne ke liye 'ye wala le lo' ya 'checkout' kahein."
                    if is_hi else
                    f"Filtered to verified **{target_col}** options:\n\n"
                    f"✓ Top match: **{top_p['name']}** (₹{int(top_p['price']):,})\n\n"
                    f"Say 'ye wala le lo' or 'checkout' to proceed with this item."
                )
            else:
                final_message = f"Koi {target_col} option nahi mila." if is_hi else f"No verified {target_col} options found."

        elif action == "FILTER_BRAND":
            from app.services.shopping_agent.deterministic_ranking import DeterministicRankingEngine
            target_br = analysis.get("brand", "Nike")
            
            all_db_prods = self.db.query(Product).filter(Product.merchant_id == self.merchant_id, Product.is_active == True).all()
            prods_dicts = []
            for p in all_db_prods:
                prods_dicts.append({
                    "id": str(p.id),
                    "name": p.name,
                    "brand": p.brand,
                    "category": p.category,
                    "subcategory": p.subcategory,
                    "price": float(p.price),
                    "mrp": float(p.mrp) if p.mrp else None,
                    "image_url": p.image_url,
                    "description": p.description,
                    "tags": p.tags or [],
                    "attributes": p.attributes or {},
                    "stock": p.inventory.stock_quantity if p.inventory else 10,
                    "rating": float(p.rating) if p.rating else 4.5,
                    "review_count": p.review_count or 0
                })

            curr_cat = active_intent.get("category")
            b_max = active_intent.get("budget_max")
            ranked = DeterministicRankingEngine.filter_and_rank(
                products=prods_dicts,
                category=curr_cat,
                budget_max=b_max,
                brand_preference=target_br
            )

            if ranked:
                discovered_products = ranked[:4]
                context_data["previous_products"] = discovered_products
                context_data["selected_product"] = discovered_products[0]
                if "active_intent" not in context_data:
                    context_data["active_intent"] = {}
                context_data["active_intent"]["brand_preference"] = target_br
                top_p = discovered_products[0]
                final_message = (
                    f"Maine **{target_br}** brand ke verified options filter kar diye hain:\n\n"
                    f"✓ Top match: **{top_p['name']}** (₹{int(top_p['price']):,})\n\n"
                    f"Isko order karne ke liye 'ye wala le lo' ya 'checkout' kahein."
                    if is_hi else
                    f"Filtered to verified **{target_br}** options:\n\n"
                    f"✓ Top match: **{top_p['name']}** (₹{int(top_p['price']):,})\n\n"
                    f"Say 'ye wala le lo' or 'checkout' to proceed."
                )
            else:
                final_message = f"Koi {target_br} option nahi mila." if is_hi else f"No verified {target_br} options found."

        elif action == "SELECT_CANDIDATE":
            target_prod = analysis.get("product") or (previous_products[0] if previous_products else None)
            if target_prod:
                context_data["selected_product"] = target_prod
                discovered_products = [target_prod]
                qty = context_data.get("quantity", 1)
                p_price = float(target_prod.get("price", 0))
                final_message = (
                    f"**{target_prod.get('name')}** (₹{int(p_price):,}) select kar liya gaya hai (Qty: {qty}). "
                    f"Aap quantity badha sakte hain ('2 pairs') ya direct 'checkout' bolkar payment start kar sakte hain."
                    if is_hi else
                    f"Selected **{target_prod.get('name')}** at ₹{int(p_price):,} (Quantity: {qty}). "
                    f"You can adjust quantity (e.g. '2 pairs') or say 'checkout' to review and pay."
                )
            else:
                final_message = "Please search for a product first."

        elif action == "SET_QUANTITY":
            qty = analysis.get("quantity", 1)
            context_data["quantity"] = qty
            target_prod = context_data.get("selected_product") or (previous_products[0] if previous_products else None)
            if target_prod:
                p_price = float(target_prod.get("price", 0))
                subtotal_calc = p_price * qty
                discovered_products = [target_prod]
                final_message = (
                    f"Quantity updated: **{qty} pairs** of **{target_prod.get('name')}** (Subtotal: ₹{int(subtotal_calc):,}). "
                    f"Order karne ke liye 'checkout' bole."
                    if is_hi else
                    f"Updated quantity to **{qty}** for **{target_prod.get('name')}** (Subtotal: ₹{int(subtotal_calc):,}). "
                    f"Say 'checkout' to proceed with your order."
                )
            else:
                final_message = f"Quantity set to {qty}."

        elif action == "APPLY_COUPON":
            c_code = analysis.get("coupon_code", "SAVE500")
            self.applied_coupon = c_code
            context_data["coupon"] = c_code
            final_message = (
                f"Coupon **{c_code}** apply kar diya gaya hai. Order review par discount reflect ho jayega."
                if is_hi else
                f"Applied coupon **{c_code}**. Discount will be calculated during order review."
            )

        elif action == "ADD_TO_CART_RESOLVED":
            target_prod = analysis.get("product", {})
            p_id = target_prod.get("id") or analysis.get("product_id")
            qty = analysis.get("quantity", 1)
            
            if p_id:
                tool_res_str = self._execute_tool("add_to_cart", {"product_id": p_id, "quantity": qty}, agent_trace_id=agent_trace.id, step_seq=step_seq)
                tool_call_count += 1
                step_seq += 1
                tool_res = json.loads(tool_res_str)
                
                if "error" not in tool_res:
                    final_message = (
                        f"**{target_prod.get('name', 'Product')}** (Qty: {qty}) aapke cart mein add kar diya gaya hai."
                        if is_hi
                        else f"Added **{target_prod.get('name', 'Product')}** (Qty: {qty}) to your cart."
                    )
                    response_actions.append("CART_UPDATED")
                    discovered_products = [target_prod]
                else:
                    final_message = tool_res["error"]
            else:
                final_message = "Product identifier not found."

        elif action == "VIRTUAL_TRY_ON":
            target_prod = analysis.get("product")
            if not target_prod and previous_products:
                target_prod = previous_products[0]

            if not target_prod:
                final_message = (
                    "Virtual Try-On ke liye please pehle koi clothing ya footwear item search ya select karein (jaise running shoes ya jackets)."
                    if is_hi
                    else "To use Virtual Try-On, please first select a clothing or footwear product (such as running shoes or athletic apparel)."
                )
            else:
                p_id = target_prod.get("id")
                prod_obj = self.db.query(Product).filter(Product.id == p_id).first()
                if prod_obj:
                    from app.services.virtual_tryon.service import VirtualTryOnService
                    eligibility = VirtualTryOnService.is_virtual_tryon_supported(prod_obj)
                    if eligibility.supported:
                        response_actions.append("OPEN_VIRTUAL_TRYON")
                        final_message = (
                            f"Maine **{prod_obj.name}** ke liye AI Virtual Try-On fitting room activate kar diya hai. "
                            f"Aap apni photo upload karke visual preview dekh sakte hain!"
                            if is_hi
                            else f"I've opened the AI Virtual Fitting Room for **{prod_obj.name}**. "
                            f"Upload a photo to preview how this {eligibility.garment_type.lower()} looks on you!"
                        )
                        discovered_products = [target_prod]
                    else:
                        final_message = (
                            f"**{prod_obj.name}** ke liye Virtual Try-On supported nahi hai: {eligibility.reason}"
                            if is_hi
                            else f"Virtual Try-On is not available for **{prod_obj.name}**: {eligibility.reason}"
                        )
                else:
                    final_message = "Selected product could not be found for virtual try-on."

        elif action == "FINALIZE_ORDER":
            # 1. Resolve Target Item
            target_scope = analysis.get("target_scope", "CANDIDATE")
            qty = analysis.get("quantity") if analysis.get("quantity", 1) > 1 else (context_data.get("quantity") or 1)
            resolved_prod_id = None
            resolved_prod_name = None

            if target_scope == "DIRECT_PRODUCT":
                q_name = analysis.get("product_name_query", "")
                matched_p = self.db.query(Product).filter(
                    Product.merchant_id == self.merchant_id,
                    Product.is_active == True,
                    (Product.name.ilike(f"%{q_name}%") | Product.description.ilike(f"%{q_name}%") | Product.category.ilike(f"%{q_name}%"))
                ).first()
                if not matched_p and context_data.get("selected_product"):
                    matched_p = self.db.query(Product).filter(Product.id == context_data["selected_product"].get("id")).first()
                if not matched_p and context_data.get("previous_products"):
                    matched_p = self.db.query(Product).filter(Product.id == context_data["previous_products"][0].get("id")).first()

                if matched_p:
                    resolved_prod_id = str(matched_p.id)
                    resolved_prod_name = matched_p.name
                else:
                    final_message = (
                        f"Mujhe '{q_name}' catalog mein nahi mila. Main aapko hamare verified options dikha sakta hoon."
                        if is_hi
                        else f"I couldn't find that exact product in the current catalog. I can show the closest verified options."
                    )

            elif target_scope in ["CANDIDATE", "PRODUCT"]:
                target_prod = analysis.get("product", {})
                resolved_prod_id = target_prod.get("id") or analysis.get("product_id") or (context_data.get("selected_product", {}).get("id") if context_data.get("selected_product") else None)
                resolved_prod_name = target_prod.get("name")

            if resolved_prod_id:
                # For direct product purchase, synchronize cart to strictly contain the targeted product and quantity
                cart_db = self.db.query(Cart).filter(
                    Cart.session_id == self.session_id,
                    Cart.merchant_id == self.merchant_id
                ).first()
                if not cart_db:
                    cart_db = Cart(session_id=self.session_id, merchant_id=self.merchant_id)
                    self.db.add(cart_db)
                    self.db.commit()
                    self.db.refresh(cart_db)

                # Delete existing items not equal to resolved_prod_id so earlier exploration candidates do not inflate quantity or total
                self.db.query(CartItem).filter(
                    CartItem.cart_id == cart_db.id,
                    CartItem.product_id != resolved_prod_id
                ).delete()
                
                target_item = self.db.query(CartItem).filter(
                    CartItem.cart_id == cart_db.id,
                    CartItem.product_id == resolved_prod_id
                ).first()
                if target_item:
                    target_item.quantity = qty
                else:
                    prod = self.db.query(Product).filter(Product.id == resolved_prod_id).first()
                    unit_price = prod.price if prod else Decimal("0.00")
                    self.db.add(CartItem(
                        cart_id=cart_db.id,
                        product_id=resolved_prod_id,
                        quantity=qty,
                        unit_price_snapshot=unit_price
                    ))
                self.db.commit()
                self.db.refresh(cart_db)
            else:
                # Fetch authoritative cart items for general cart checkout
                cart_db = self.db.query(Cart).filter(
                    Cart.session_id == self.session_id,
                    Cart.merchant_id == self.merchant_id
                ).first()

            if not cart_db or not cart_db.items or len(cart_db.items) == 0:
                final_message = (
                    "Aapka cart abhi khali hai. Please batayein aap kya khareedna chahte hain!"
                    if is_hi
                    else "Your cart is currently empty. Please choose a product to order!"
                )
            else:
                # 2. Re-validate Product Existence & Live Stock Inventory
                stock_valid = True
                stock_err = None
                for it in cart_db.items:
                    prod = self.db.query(Product).filter(Product.id == it.product_id, Product.merchant_id == self.merchant_id).first()
                    if not prod or not prod.is_active:
                        stock_valid = False
                        stock_err = f"Product '{it.product_id}' is inactive or unavailable."
                        break
                    inv = self.db.query(Inventory).filter(Inventory.product_id == it.product_id, Inventory.merchant_id == self.merchant_id).first()
                    if not inv or inv.stock_quantity < it.quantity:
                        stock_valid = False
                        stock_err = (
                            f"'{prod.name}' ki requested quantity ({it.quantity}) stock mein available nahi hai. Maine checkout pause kar diya hai."
                            if is_hi
                            else f"One of the products is no longer available in the requested quantity. I've paused checkout so we can update the order."
                        )
                        break

                if not stock_valid:
                    final_message = stock_err or "Stock verification failed."
                else:
                    # 3. Calculate Deterministic Pricing Breakdown
                    pricing = PricingService.calculate_authoritative_pricing(
                        db=self.db,
                        merchant_id=self.merchant_id,
                        session_id=self.session_id,
                        user=self.user,
                        coupon_code=self.applied_coupon or context_data.get("coupon"),
                        voucher_code=self.applied_voucher or context_data.get("voucher"),
                        use_coins=self.use_coins or context_data.get("use_coins", False)
                    )

                    # 4. Delivery Address Verification
                    addr = self.delivery_address or context_data.get("delivery_address")
                    addr_valid = False
                    if addr and isinstance(addr, dict):
                        addr_valid = bool(
                            addr.get("full_name") and
                            addr.get("address_line1") and
                            addr.get("city") and
                            addr.get("state") and
                            addr.get("pin_code")
                        )

                    # 5. Threshold Governance Check
                    total_amount = float(pricing.total)
                    total_qty = sum(it.quantity for it in cart_db.items)

                    # Hard Firewall Boundary: Max ₹10,000 or Max 5 units
                    if total_amount > 10000.0 or total_qty > 5:
                        final_message = (
                            f"Governance Policy Blocked: Order total (₹{total_amount:,.2f}) or quantity ({total_qty} units) exceeds safety limits (Max ₹10,000 / Max 5 units). Transaction blocked."
                            if not is_hi else
                            f"Policy Block: Order total (₹{total_amount:,.2f}) ya quantity ({total_qty}) policy limits (Max ₹10,000 / 5 units) se jyada hai. Transaction blocked."
                        )
                        return ChatResponse(
                            session_id=self.session_id,
                            message=final_message,
                            products=[],
                            cart=get_cart(db=self.db, merchant_id=self.merchant_id, session_id=self.session_id),
                            recommendations=[],
                            actions=["POLICY_BLOCKED"],
                            structured_intent={"action": "blocked_by_governance", "total": total_amount, "quantity": total_qty},
                            requires_approval=False,
                            trace_id=self.trace_id
                        )

                    autonomous_threshold = 5000.0
                    is_above_threshold = total_amount > autonomous_threshold
                    requires_approval = is_above_threshold

                    if is_above_threshold:
                        approval_details = {
                            "amount": total_amount,
                            "threshold": autonomous_threshold,
                            "reason": f"Order total (₹{total_amount:,.2f}) exceeds autonomous limit of ₹5,000.00."
                        }

                    # Construct OrderReview items
                    review_items: List[OrderReviewItem] = []
                    for it in cart_db.items:
                        prod = self.db.query(Product).filter(Product.id == it.product_id).first()
                        p_price = float(it.unit_price_snapshot)
                        review_items.append(OrderReviewItem(
                            product_id=it.product_id,
                            name=prod.name if prod else "Athletic Product",
                            quantity=it.quantity,
                            price=p_price,
                            subtotal=p_price * it.quantity,
                            category=prod.category if prod else "Gear",
                            image_url=(prod.attributes.get("image_url") if prod and prod.attributes else None)
                        ))

                    order_review_obj = OrderReview(
                        items=review_items,
                        subtotal=float(pricing.subtotal),
                        coupon_code=pricing.coupon_code,
                        coupon_discount=float(pricing.coupon_discount),
                        voucher_code=pricing.voucher_code,
                        voucher_discount=float(pricing.voucher_discount),
                        coins_used=pricing.coins_used,
                        coin_discount=float(pricing.coin_discount),
                        shipping=0.0,
                        total=total_amount,
                        currency="INR",
                        delivery_address=addr if addr_valid else None,
                        delivery_address_required=not addr_valid,
                        autonomous_threshold=autonomous_threshold,
                        is_above_threshold=is_above_threshold,
                        potential_points=pricing.points_to_earn
                    )

                    structured_intent = {
                        "intent": "purchase",
                        "action": "finalize_order",
                        "product_ids": [it.product_id for it in cart_db.items],
                        "selected_product_id": resolved_prod_id or (cart_db.items[0].product_id if cart_db.items else None),
                        "quantity": qty,
                        "requires_confirmation": True,
                        "requires_payment": True
                    }

                    # 6. Response Wording
                    if not addr_valid:
                        final_message = (
                            f"Maine aapka order review ready kar diya hai (Total: ₹{total_amount:,.2f}). "
                            f"Order place karne se pehle, mujhe aapka delivery address chahiye. Please apna address provide karein."
                            if is_hi
                            else f"I have prepared your order review (Total: ₹{total_amount:,.2f}). "
                            f"Before I place the order, I need your delivery address. Please enter your delivery details."
                        )
                    elif is_above_threshold:
                        final_message = (
                            f"Aapka order total ₹{total_amount:,.2f} hai. Ye aapki ₹5,000 autonomous limit se above hai, "
                            f"isliye payment se pehle aapki explicit approval chahiye."
                            if is_hi
                            else f"Your order total is ₹{total_amount:,.2f}, which exceeds the autonomous spending limit of ₹5,000. "
                            f"Your explicit approval is required before payment."
                        )
                    else:
                        item_names = ", ".join([f"**{it.name}**" for it in review_items])
                        final_message = (
                            f"Maine aapka order review tayyar kar diya hai ({item_names}). "
                            f"Total payable amount ₹{total_amount:,.2f} hai. Direct Razorpay payment ke liye [Confirm & Pay] par click karein."
                            if is_hi
                            else f"I've prepared your order review for {item_names}. "
                            f"Total payable is ₹{total_amount:,.2f}. Please review and click [Confirm & Pay] to proceed to secure Razorpay checkout."
                        )

                    response_actions.append("ORDER_REVIEW_CREATED")
                    if is_above_threshold:
                        response_actions.append("APPROVAL_REQUIRED")

                    # Record Structured Audit Trail
                    AuditService.record_event(
                        db=self.db,
                        merchant_id=self.merchant_id,
                        trace_id=self.trace_id,
                        session_id=self.session_id,
                        agent_id=self.agent_id,
                        agent_version=self.agent_version,
                        actor_type="AGENT",
                        action="AI_PURCHASE_INTENT",
                        event_type="AI_PURCHASE_INTENT",
                        status="SUCCESS",
                        metadata_json={
                            "structured_intent": structured_intent,
                            "items_count": len(review_items),
                            "subtotal": float(pricing.subtotal),
                            "total": total_amount,
                            "is_above_threshold": is_above_threshold
                        }
                    )
                    AuditService.record_event(
                        db=self.db,
                        merchant_id=self.merchant_id,
                        trace_id=self.trace_id,
                        session_id=self.session_id,
                        agent_id=self.agent_id,
                        agent_version=self.agent_version,
                        actor_type="AGENT",
                        action="ORDER_REVIEW_CREATED",
                        event_type="ORDER_REVIEW_CREATED",
                        status="SUCCESS",
                        metadata_json={
                            "total": total_amount,
                            "currency": "INR",
                            "is_above_threshold": is_above_threshold
                        }
                    )

        elif analysis.get("search_params"):
            from app.services.shopping_agent.deterministic_ranking import DeterministicRankingEngine
            search_params = analysis["search_params"]
            updated_intent = analysis["active_intent"]
            
            # Execute authoritative search tool
            tool_res_str = self._execute_tool("search_products", search_params, agent_trace_id=agent_trace.id, step_seq=step_seq)
            tool_call_count += 1
            step_seq += 1
            
            tool_res = json.loads(tool_res_str)
            raw_results = tool_res.get("results", [])
            
            # Deterministic Ranking with Hard Filters First
            ranked_results = DeterministicRankingEngine.filter_and_rank(
                products=raw_results,
                category=updated_intent.get("category"),
                subcategory=updated_intent.get("subcategory"),
                budget_max=search_params.get("max_price"),
                budget_min=search_params.get("min_price"),
                brand_preference=search_params.get("brand") or updated_intent.get("brand_preference"),
                colour_preference=search_params.get("colour") or updated_intent.get("colour_preference"),
                use_case=search_params.get("use_case") or updated_intent.get("use_case"),
                in_stock_only=True
            )

            if ranked_results:
                discovered_products = ranked_results
                context_data["active_intent"] = updated_intent
                context_data["previous_products"] = ranked_results
                context_data["selected_product"] = ranked_results[0]
                
                prod_type = updated_intent.get("product_type", "options")
                max_p = search_params.get("max_price")
                
                if is_hi:
                    if len(ranked_results) == 1:
                        p = ranked_results[0]
                        final_message = (
                            f"Hamare paas **{p['name']}** (₹{int(p['price']):,}) available hai. "
                            f"Verified stock ({p.get('stock_quantity', 1)} in stock) aur direct order kar sakte hain."
                        )
                    else:
                        names = [f"**{r['name']}** (₹{int(r['price']):,})" for r in ranked_results[:3]]
                        summary_str = ", ".join(names[:-1]) + f", aur {names[-1]}" if len(names) > 2 else " aur ".join(names)
                        if max_p:
                            final_message = (
                                f"Bilkul! ₹{int(max_p):,} ke andar hamare paas ye {len(ranked_results)} verified {prod_type.lower()} options hain: "
                                f"{summary_str}. Sabhi options real-time verified stock mein hain."
                            )
                        else:
                            final_message = (
                                f"Bilkul! Hamare collection mein ye {len(ranked_results)} verified {prod_type.lower()} options hain: "
                                f"{summary_str}. Sabhi options real-time verified stock mein hain."
                            )
                else:
                    if len(ranked_results) == 1:
                        p = ranked_results[0]
                        final_message = (
                            f"I found **{p['name']}** at ₹{int(p['price']):,} in our {p.get('category')} collection. "
                            f"Verified in stock ({p.get('stock_quantity', 1)} available) and ready to order."
                        )
                    else:
                        names = [f"**{r['name']}** (₹{int(r['price']):,})" for r in ranked_results[:3]]
                        summary_str = ", ".join(names[:-1]) + f", and {names[-1]}" if len(names) > 2 else " and ".join(names)
                        if max_p:
                            final_message = (
                                f"Here are {len(ranked_results)} verified {prod_type.lower()} under ₹{int(max_p):,}: "
                                f"{summary_str}. All options are in stock and verified against our real-time inventory."
                            )
                        else:
                            final_message = (
                                f"Here are {len(ranked_results)} verified {prod_type.lower()} options: "
                                f"{summary_str}. All options are in stock and verified against our real-time inventory."
                            )
            else:
                # 0 products found in active category
                discovered_products = []
                context_data["active_intent"] = updated_intent
                
                prod_type = updated_intent.get("product_type", "products")
                max_p = search_params.get("max_price")
                
                target_cat = updated_intent.get("category")
                closest = None
                if target_cat:
                    if target_cat.lower() in ["running", "footwear"]:
                        closest = self.db.query(Product).filter(
                            Product.merchant_id == self.merchant_id,
                            Product.is_active == True,
                            (Product.category.ilike("%running%") | Product.category.ilike("%footwear%") | Product.name.ilike("%running%") | Product.name.ilike("%shoes%") | Product.name.ilike("%marathon%"))
                        ).order_by(Product.price.asc()).first()
                    else:
                        closest = self.db.query(Product).filter(
                            Product.merchant_id == self.merchant_id,
                            Product.is_active == True,
                            Product.category.ilike(f"%{target_cat}%")
                        ).order_by(Product.price.asc()).first()
                
                if closest and max_p:
                    if is_hi:
                        final_message = (
                            f"Mujhe ₹{int(max_p):,} ke aas-paas {prod_type.lower()} nahi mile. "
                            f"Hamare catalog mein verified {prod_type.lower()} ₹{int(closest.price):,} ({closest.name}) se shuru hote hain."
                        )
                    else:
                        final_message = (
                            f"I couldn't find {prod_type.lower()} around ₹{int(max_p):,} in the current catalog. "
                            f"The closest verified {prod_type.lower()} options start at ₹{int(closest.price):,} ({closest.name})."
                        )
                else:
                    if is_hi:
                        final_message = f"Maine catalog check kiya par {prod_type.lower()} ke matching options nahi mile."
                    else:
                        final_message = f"I searched our catalog but couldn't find any {prod_type.lower()} matching those specific constraints."
            
            structured_intent = {
                "query": search_params.get("query") or (f"{updated_intent.get('category')} under ₹{int(search_params['max_price']):,}" if search_params.get("max_price") else updated_intent.get("category", "Products")),
                "category": updated_intent.get("category"),
                "max_price": search_params.get("max_price"),
                "min_price": search_params.get("min_price"),
                "quantity": 1,
                "sort": None,
                "in_stock_only": False,
                "clarification_needed": False
            }
        else:
            final_message = analysis.get("message", "How can I assist your shopping today?")
            structured_intent = analysis.get("structured_intent")

        # 4. Update session history & commit context_data
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": final_message})
        context_data["history"] = history[-10:]
        
        session.context_data = context_data
        self.db.commit()

        # 5. Retrieve authoritative cart state
        cart_state = get_cart(db=self.db, merchant_id=self.merchant_id, session_id=self.session_id)

        # 6. Complete Agent Trace
        AgentTracingService.complete_agent_trace(
            db=self.db,
            agent_trace_id=agent_trace.id,
            status="SUCCESS",
            output_data={"response": final_message, "products_count": len(discovered_products)},
            token_usage=120,
            tool_call_count=tool_call_count
        )

        return ChatResponse(
            session_id=self.session_id,
            message=final_message,
            products=discovered_products,
            cart=cart_state,
            recommendations=[],
            actions=response_actions,
            structured_intent=structured_intent,
            order_review=order_review_obj,
            requires_approval=requires_approval,
            approval_details=approval_details,
            trace_id=self.trace_id
        )
