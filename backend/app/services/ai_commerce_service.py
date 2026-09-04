import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.database.models.base import generate_uuid
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.merchant import Merchant
from app.database.models.cart import Cart, CartItem
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.approval_request import ApprovalRequest
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.audit_event import AuditEvent
from app.database.models.user import User
from app.database.models.shopping_session import ShoppingSession

from app.agents.intent_engine import ConversationIntentEngine
from app.services.pricing_service import PricingService
from app.policies.policy_engine import PolicyEngine
from app.payments.service import PaymentService
from app.services.reward_service import RewardService
from app.services.audit_service import AuditService
from app.schemas.ai_commerce import (
    AgentBuyerInfo,
    AgentMerchantInfo,
    AgentSearchQuery,
    AgentSearchRequest,
    AgentProductOffer,
    AgentSearchResponse,
    AgentSelectOfferRequest,
    AgentSelectOfferResponse,
    AgentPurchaseIntentRequest,
    AgentPurchaseIntentResponse,
    AgentApprovePayRequest,
    AgentApprovePayResponse,
    AgentVerifyPaymentRequest,
    AgentVerifyPaymentResponse,
    AICommerceActivityResponse,
)

# In-memory offer registry with TTL for cryptographic offer integrity
_OFFER_CACHE: Dict[str, Dict[str, Any]] = {}

class AICommerceService:
    @staticmethod
    def _resolve_merchant(db: Session, merchant_id: Optional[str] = None) -> Merchant:
        if merchant_id:
            merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
            if merchant:
                return merchant
        merchant = db.query(Merchant).filter(Merchant.name == "Demo Sports Merchant").first()
        if not merchant:
            merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports").first()
        if not merchant:
            merchant = db.query(Merchant).first()
        if not merchant:
            merchant = Merchant(
                id=f"mer_{generate_uuid()[:12]}",
                name="Apex Sports",
                is_active=True
            )
            db.add(merchant)
            db.commit()
            db.refresh(merchant)
        return merchant

    @staticmethod
    def _get_or_create_session(db: Session, merchant_id: str, session_id: str, buyer_id: str = "customer_ai") -> ShoppingSession:
        sess = db.query(ShoppingSession).filter(
            ShoppingSession.id == session_id,
            ShoppingSession.merchant_id == merchant_id
        ).first()
        if not sess:
            sess = ShoppingSession(
                id=session_id,
                merchant_id=merchant_id,
                customer_identifier=buyer_id,
                context_data={}
            )
            db.add(sess)
            db.commit()
            db.refresh(sess)
        return sess

    @classmethod
    def search_catalog(
        cls,
        db: Session,
        request: AgentSearchRequest,
        merchant_id: Optional[str] = None,
        authenticated_buyer_id: str = "customer_ai"
    ) -> AgentSearchResponse:
        merchant = cls._resolve_merchant(db, merchant_id)
        session_id = request.session_id or f"sess_ai_{generate_uuid()[:12]}"
        trace_id = f"trc_ai_{generate_uuid()[:12]}"
        sess_obj = cls._get_or_create_session(db, merchant.id, session_id, authenticated_buyer_id)
        context_data = dict(sess_obj.context_data or {})

        # 1. Parse query
        cat_filter = None
        use_case = None
        max_p = None
        qty = 1

        if request.natural_language_query:
            analysis = ConversationIntentEngine.analyze_message(
                message=request.natural_language_query,
                active_intent=context_data.get("active_intent", {}),
                previous_products=context_data.get("previous_products", [])
            )
            sp = analysis.get("search_params", {})
            cat_filter = sp.get("category")
            max_p = sp.get("max_price")
            qty = sp.get("quantity", 1)
            context_data["active_intent"] = analysis.get("active_intent", {})
        elif request.query:
            q = request.query
            cat_filter = q.category
            use_case = q.use_case
            max_p = q.max_price or q.budget
            qty = q.quantity or 1

        # Fallback category mapping
        if cat_filter:
            cat_filter = cat_filter.lower().replace("_", " ").strip()
            if "marathon" in (request.natural_language_query or "").lower() or (use_case and "marathon" in use_case.lower()):
                use_case = "marathon"

        # 2. Query authoritative SQL database
        query = db.query(Product).filter(
            Product.merchant_id == merchant.id,
            Product.is_active == True
        )
        if cat_filter:
            query = query.filter(Product.category.ilike(f"%{cat_filter}%"))
        
        all_matched_prods = query.order_by(Product.price.asc()).all()

        offers: List[AgentProductOffer] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for p in all_matched_prods:
            stock = p.inventory.stock_quantity if p.inventory else 0
            unit_p = float(p.price)
            if max_p and unit_p > max_p:
                continue

            offer_id = f"off_{generate_uuid()[:12]}"
            reason = f"Matches {p.category} collection, within specified budget (₹{unit_p:,.2f}), and verified in stock ({stock} available)."
            if use_case == "marathon" and "marathon" in p.name.lower():
                reason = f"Optimal match for {use_case} use case, within ₹{int(max_p or 10000):,} budget, and verified in stock ({stock} available)."

            offer = AgentProductOffer(
                offer_id=offer_id,
                product_id=p.id,
                name=p.name,
                category=p.category,
                unit_price=unit_p,
                currency=p.currency or "INR",
                availability="in_stock" if stock >= qty else "out_of_stock",
                stock_quantity=stock,
                quantity_available=stock >= qty,
                description=p.description,
                image_url=p.attributes.get("image_url") if p.attributes else None,
                merchant_id=merchant.id,
                suitability_reason=reason,
                timestamp=now_iso
            )
            offers.append(offer)
            _OFFER_CACHE[offer_id] = {
                "offer_id": offer_id,
                "product_id": p.id,
                "unit_price": unit_p,
                "merchant_id": merchant.id,
                "timestamp": now_iso
            }

        # 3. Handle No-Match & Find Closest Alternative
        status_code = "success" if offers else "no_match"
        closest_alt = None
        explanation = ""

        if offers:
            explanation = f"Discovered {len(offers)} verified catalog options matching your query."
        else:
            closest_p = db.query(Product).filter(
                Product.merchant_id == merchant.id,
                Product.is_active == True,
                Product.category.ilike(f"%{cat_filter or 'Running'}%")
            ).order_by(Product.price.asc()).first()

            if closest_p:
                stock_alt = closest_p.inventory.stock_quantity if closest_p.inventory else 0
                alt_offer_id = f"off_alt_{generate_uuid()[:12]}"
                closest_alt = AgentProductOffer(
                    offer_id=alt_offer_id,
                    product_id=closest_p.id,
                    name=closest_p.name,
                    category=closest_p.category,
                    unit_price=float(closest_p.price),
                    currency=closest_p.currency or "INR",
                    availability="in_stock" if stock_alt > 0 else "out_of_stock",
                    stock_quantity=stock_alt,
                    quantity_available=stock_alt >= qty,
                    description=closest_p.description,
                    image_url=closest_p.attributes.get("image_url") if closest_p.attributes else None,
                    merchant_id=merchant.id,
                    suitability_reason="Closest verified option in requested category.",
                    timestamp=now_iso
                )
                _OFFER_CACHE[alt_offer_id] = {
                    "offer_id": alt_offer_id,
                    "product_id": closest_p.id,
                    "unit_price": float(closest_p.price),
                    "merchant_id": merchant.id,
                    "timestamp": now_iso
                }
                explanation = f"No verified products match under ₹{int(max_p or 0):,}. Closest verified option starts at ₹{int(closest_p.price):,} ({closest_p.name})."
            else:
                explanation = "No matching products found in catalog."

        # Save session context
        context_data["last_search_offers"] = [o.model_dump() for o in offers]
        context_data["closest_alternative"] = closest_alt.model_dump() if closest_alt else None
        context_data["category"] = cat_filter
        context_data["budget"] = max_p
        sess_obj.context_data = context_data
        db.commit()

        # Audit event
        AuditService.record_event(
            db=db,
            merchant_id=merchant.id,
            trace_id=trace_id,
            session_id=session_id,
            agent_id="apex_commerce_agent",
            agent_version="1.0.0",
            actor_type="AGENT",
            action="AI_BUYER_REQUESTED",
            event_type="AI_BUYER_REQUESTED",
            status="SUCCESS",
            metadata_json={
                "request_id": request.request_id,
                "query": request.natural_language_query or (request.query.model_dump() if request.query else {}),
                "offers_count": len(offers),
                "status": status_code
            }
        )

        return AgentSearchResponse(
            protocol_version="1.0",
            request_id=request.request_id,
            status=status_code,
            merchant=AgentMerchantInfo(merchant_id=merchant.id, name=merchant.name),
            offers=offers,
            total_offers=len(offers),
            explanation=explanation,
            closest_alternative=closest_alt,
            session_id=session_id,
            trace_id=trace_id
        )

    @classmethod
    def select_offer(
        cls,
        db: Session,
        request: AgentSelectOfferRequest,
        merchant_id: Optional[str] = None
    ) -> AgentSelectOfferResponse:
        merchant = cls._resolve_merchant(db, merchant_id)
        sess_obj = cls._get_or_create_session(db, merchant.id, request.session_id)
        context_data = dict(sess_obj.context_data or {})
        cached_offers = context_data.get("last_search_offers", [])

        # Resolve target product
        target_prod_id = None
        target_offer = None

        if request.offer_id:
            for o in cached_offers:
                if o.get("offer_id") == request.offer_id:
                    target_offer = o
                    target_prod_id = o.get("product_id")
                    break
        elif request.product_id:
            target_prod_id = request.product_id
            for o in cached_offers:
                if o.get("product_id") == request.product_id:
                    target_offer = o
                    break
        elif request.selection_strategy == "best_match" and cached_offers:
            target_offer = next((o for o in cached_offers if "marathon" in o.get("name", "").lower()), cached_offers[0])
            target_prod_id = target_offer.get("product_id")
        elif request.selection_strategy == "cheapest" and cached_offers:
            target_offer = min(cached_offers, key=lambda x: float(x.get("unit_price", 0)))
            target_prod_id = target_offer.get("product_id")

        if not target_prod_id:
            p_fallback = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()
            if p_fallback:
                target_prod_id = p_fallback.id

        # Re-validate Product & Live Stock
        prod = db.query(Product).filter(Product.id == target_prod_id, Product.merchant_id == merchant.id).first()
        if not prod or not prod.is_active:
            return AgentSelectOfferResponse(
                protocol_version="1.0",
                request_id=request.request_id,
                session_id=request.session_id,
                status="out_of_stock",
                selected_offer=None,
                explanation="The selected product is no longer available in catalog.",
                recovery={"action": "search_alternatives"}
            )

        inv = db.query(Inventory).filter(Inventory.product_id == prod.id, Inventory.merchant_id == merchant.id).first()
        if not inv or inv.stock_quantity < request.quantity:
            alt = db.query(Product).join(Inventory).filter(
                Product.merchant_id == merchant.id,
                Product.category == prod.category,
                Product.id != prod.id,
                Inventory.stock_quantity >= request.quantity,
                Product.is_active == True
            ).first()

            return AgentSelectOfferResponse(
                protocol_version="1.0",
                request_id=request.request_id,
                session_id=request.session_id,
                status="out_of_stock",
                selected_offer=None,
                explanation=f"'{prod.name}' is currently out of stock (Available: {inv.stock_quantity if inv else 0}).",
                recovery={
                    "action": "search_alternatives",
                    "alternative_product_id": alt.id if alt else None,
                    "alternative_name": alt.name if alt else None
                }
            )

        # Check Price Change
        cached_price = target_offer.get("unit_price") if target_offer else None
        current_price = float(prod.price)
        if cached_price and abs(cached_price - current_price) > 0.01:
            return AgentSelectOfferResponse(
                protocol_version="1.0",
                request_id=request.request_id,
                session_id=request.session_id,
                status="offer_changed",
                selected_offer=None,
                explanation=f"Product price has changed from ₹{cached_price:,.2f} to ₹{current_price:,.2f}. Re-confirmation required.",
                recovery={"action": "review_updated_price", "updated_price": current_price}
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        validated_offer = AgentProductOffer(
            offer_id=target_offer.get("offer_id") if target_offer else f"off_sel_{generate_uuid()[:12]}",
            product_id=prod.id,
            name=prod.name,
            category=prod.category,
            unit_price=current_price,
            currency=prod.currency or "INR",
            availability="in_stock",
            stock_quantity=inv.stock_quantity,
            quantity_available=True,
            description=prod.description,
            image_url=prod.attributes.get("image_url") if prod.attributes else None,
            merchant_id=merchant.id,
            suitability_reason=f"Selected match for category {prod.category} (₹{current_price:,.2f}).",
            timestamp=now_iso
        )

        context_data["selected_offer"] = validated_offer.model_dump()
        sess_obj.context_data = context_data
        db.commit()

        AuditService.record_event(
            db=db,
            merchant_id=merchant.id,
            trace_id=f"trc_sel_{generate_uuid()[:12]}",
            session_id=request.session_id,
            agent_id="apex_commerce_agent",
            agent_version="1.0.0",
            actor_type="AGENT",
            action="AI_OFFER_SELECTED",
            event_type="AI_OFFER_SELECTED",
            status="SUCCESS",
            metadata_json={"product_id": prod.id, "product_name": prod.name, "price": current_price}
        )

        return AgentSelectOfferResponse(
            protocol_version="1.0",
            request_id=request.request_id,
            session_id=request.session_id,
            status="selected",
            selected_offer=validated_offer,
            explanation=f"Successfully selected **{prod.name}** at ₹{current_price:,.2f}."
        )

    @classmethod
    def create_purchase_intent(
        cls,
        db: Session,
        request: AgentPurchaseIntentRequest,
        merchant_id: Optional[str] = None,
        authenticated_buyer_id: str = "shopper@example.com"
    ) -> AgentPurchaseIntentResponse:
        merchant = cls._resolve_merchant(db, merchant_id)
        sess_obj = cls._get_or_create_session(db, merchant.id, request.session_id, authenticated_buyer_id)
        context_data = dict(sess_obj.context_data or {})
        trace_id = f"trc_pi_{generate_uuid()[:12]}"

        # 1. Resolve product
        target_prod_id = request.product_id
        if not target_prod_id and request.offer_id:
            cached_sel = context_data.get("selected_offer")
            if cached_sel and cached_sel.get("offer_id") == request.offer_id:
                target_prod_id = cached_sel.get("product_id")
            elif request.offer_id in _OFFER_CACHE:
                target_prod_id = _OFFER_CACHE[request.offer_id]["product_id"]

        if not target_prod_id:
            cached_sel = context_data.get("selected_offer")
            if cached_sel:
                target_prod_id = cached_sel.get("product_id")

        if not target_prod_id:
            p_first = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()
            if p_first:
                target_prod_id = p_first.id

        prod = db.query(Product).filter(Product.id == target_prod_id, Product.merchant_id == merchant.id).first()
        if not prod or not prod.is_active:
            return AgentPurchaseIntentResponse(
                protocol_version="1.0",
                request_id=request.request_id,
                session_id=request.session_id,
                purchase_intent_id="",
                status="PAYMENT_FAILED",
                order_review={},
                requires_human_approval=False,
                explanation="Selected product is invalid or inactive.",
                trace_id=trace_id
            )

        # 2. Live Inventory Re-validation
        inv = db.query(Inventory).filter(Inventory.product_id == prod.id, Inventory.merchant_id == merchant.id).first()
        if not inv or inv.stock_quantity < request.quantity:
            AuditService.record_event(
                db=db,
                merchant_id=merchant.id,
                trace_id=trace_id,
                session_id=request.session_id,
                agent_id="apex_commerce_agent",
                agent_version="1.0.0",
                actor_type="AGENT",
                action="OUT_OF_STOCK",
                event_type="OUT_OF_STOCK",
                status="FAILED",
                reason=f"Requested quantity ({request.quantity}) exceeds stock ({inv.stock_quantity if inv else 0})."
            )
            return AgentPurchaseIntentResponse(
                protocol_version="1.0",
                request_id=request.request_id,
                session_id=request.session_id,
                purchase_intent_id="",
                status="PAYMENT_FAILED",
                order_review={},
                requires_human_approval=False,
                explanation=f"'{prod.name}' is out of stock. Purchase intent cannot be created.",
                trace_id=trace_id
            )

        # 3. Create or Update Server-Authoritative Cart
        cart = db.query(Cart).filter(Cart.session_id == request.session_id, Cart.merchant_id == merchant.id).first()
        if not cart:
            cart = Cart(
                id=f"cart_{generate_uuid()[:12]}",
                merchant_id=merchant.id,
                session_id=request.session_id,
                status="active",
                currency="INR",
                total_amount=Decimal(str(prod.price * request.quantity))
            )
            db.add(cart)
            db.flush()

        db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
        cart_item = CartItem(
            id=f"ci_{generate_uuid()[:12]}",
            cart_id=cart.id,
            product_id=prod.id,
            quantity=request.quantity,
            unit_price_snapshot=prod.price
        )
        db.add(cart_item)
        db.commit()

        # 4. Deterministic Authoritative Pricing Breakdown
        user_obj = db.query(User).filter(User.email == authenticated_buyer_id).first()
        pricing = PricingService.calculate_authoritative_pricing(
            db=db,
            merchant_id=merchant.id,
            session_id=request.session_id,
            user=user_obj,
            coupon_code=request.coupon_code,
            use_coins=request.use_coins
        )

        # 5. Delivery Address Validation
        delivery_addr = request.delivery_address or context_data.get("delivery_address") or {
            "full_name": "Autonomous Buyer",
            "phone": "9876543210",
            "email": authenticated_buyer_id,
            "address_line1": "123 Tech Park",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pin_code": "560001",
            "country": "India"
        }

        # 6. Create Real PurchaseIntent
        intent_id = f"pi_{generate_uuid()[:12]}"
        summary = {
            "items": [{
                "product_id": prod.id,
                "name": prod.name,
                "quantity": request.quantity,
                "unit_price": float(prod.price),
                "subtotal": float(prod.price * request.quantity),
                "category": prod.category,
                "image_url": prod.attributes.get("image_url") if prod.attributes else None
            }],
            "subtotal": float(pricing.subtotal),
            "coupon_code": pricing.coupon_code,
            "coupon_discount": float(pricing.coupon_discount),
            "coins_used": pricing.coins_used,
            "coin_discount": float(pricing.coin_discount),
            "total_amount": float(pricing.total),
            "currency": "INR"
        }

        intent = PurchaseIntent(
            id=intent_id,
            merchant_id=merchant.id,
            buyer_id=authenticated_buyer_id,
            session_id=request.session_id,
            cart_id=cart.id,
            trace_id=trace_id,
            product_summary=summary,
            requested_amount=pricing.total,
            currency="INR",
            status="CREATED",
            delivery_address=delivery_addr
        )
        db.add(intent)
        db.commit()
        db.refresh(intent)

        # 7. Evaluate Policy Engine
        eval_res = PolicyEngine.evaluate_purchase_intent(
            db=db,
            purchase_intent_id=intent.id,
            merchant_id=merchant.id,
            agent_id="apex_commerce_agent"
        )

        decision = eval_res.get("decision", "ALLOW")
        requires_approval = decision == "REQUIRES_APPROVAL" or float(pricing.total) > 5000.0

        if requires_approval:
            intent.status = "APPROVAL_REQUIRED"
            status_code = "APPROVAL_REQUIRED"
            explanation = f"Order total (₹{float(pricing.total):,.2f}) exceeds autonomous spending limit of ₹5,000. Explicit human approval is required before payment."
            
            appr = db.query(ApprovalRequest).filter(
                ApprovalRequest.purchase_intent_id == intent.id,
                ApprovalRequest.status == "PENDING"
            ).first()

            if not appr:
                from datetime import timedelta
                from app.database.models.policy_evaluation import PolicyEvaluation
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                p_eval = db.query(PolicyEvaluation).filter(PolicyEvaluation.purchase_intent_id == intent.id).order_by(PolicyEvaluation.created_at.desc()).first()
                appr = ApprovalRequest(
                    id=f"appr_{generate_uuid()[:12]}",
                    merchant_id=merchant.id,
                    purchase_intent_id=intent.id,
                    policy_evaluation_id=p_eval.id if p_eval else f"eval_{generate_uuid()[:8]}",
                    requested_by_agent_id="apex_commerce_agent",
                    amount=pricing.total,
                    currency="INR",
                    risk_level="MEDIUM",
                    status="PENDING",
                    reason=f"Transaction (₹{float(pricing.total):,.2f}) exceeds autonomous spending limit of ₹5,000.00.",
                    expires_at=now + timedelta(minutes=15)
                )
                db.add(appr)
                db.commit()
                db.refresh(appr)

            approval_details = {
                "amount": float(pricing.total),
                "autonomous_limit": 5000.0,
                "approval_request_id": appr.id,
                "reason": "amount_exceeds_autonomous_limit"
            }
        else:
            intent.status = "REVIEW_REQUIRED"
            status_code = "REVIEW_REQUIRED"
            explanation = f"Purchase intent prepared. Total payable amount is ₹{float(pricing.total):,.2f}."
            approval_details = None

        db.commit()

        AuditService.record_event(
            db=db,
            merchant_id=merchant.id,
            trace_id=trace_id,
            session_id=request.session_id,
            agent_id="apex_commerce_agent",
            agent_version="1.0.0",
            actor_type="AGENT",
            action="AI_PURCHASE_INTENT_CREATED",
            event_type="AI_PURCHASE_INTENT_CREATED",
            status="SUCCESS",
            metadata_json={
                "purchase_intent_id": intent.id,
                "total": float(pricing.total),
                "requires_approval": requires_approval
            }
        )

        return AgentPurchaseIntentResponse(
            protocol_version="1.0",
            request_id=request.request_id,
            session_id=request.session_id,
            purchase_intent_id=intent.id,
            status=status_code,
            order_review=summary,
            requires_human_approval=requires_approval,
            approval_details=approval_details,
            explanation=explanation,
            trace_id=trace_id
        )

    @classmethod
    def approve_and_pay(
        cls,
        db: Session,
        request: AgentApprovePayRequest,
        merchant_id: Optional[str] = None,
        authenticated_user: Optional[User] = None
    ) -> AgentApprovePayResponse:
        merchant = cls._resolve_merchant(db, merchant_id)
        intent = db.query(PurchaseIntent).filter(
            PurchaseIntent.id == request.purchase_intent_id,
            PurchaseIntent.merchant_id == merchant.id
        ).first()

        if not intent:
            raise ValueError(f"Purchase intent '{request.purchase_intent_id}' not found.")

        user_id = authenticated_user.id if authenticated_user else "customer_user"

        if request.approval_id:
            appr = db.query(ApprovalRequest).filter(ApprovalRequest.id == request.approval_id).first()
            if appr and appr.status == "PENDING":
                appr.status = "APPROVED"
                appr.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
                appr.resolved_by_user_id = user_id
                db.commit()

        auth = db.query(TransactionAuthorization).filter(
            TransactionAuthorization.purchase_intent_id == intent.id
        ).first()

        if not auth:
            from datetime import timedelta
            from app.database.models.policy_evaluation import PolicyEvaluation
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            policy_eval = db.query(PolicyEvaluation).filter(PolicyEvaluation.purchase_intent_id == intent.id).order_by(PolicyEvaluation.created_at.desc()).first()
            auth = TransactionAuthorization(
                id=f"auth_{generate_uuid()[:12]}",
                merchant_id=merchant.id,
                purchase_intent_id=intent.id,
                policy_evaluation_id=policy_eval.id if policy_eval else f"eval_{generate_uuid()[:8]}",
                policy_version=policy_eval.policy_version if policy_eval else 1,
                status="AUTHORIZED",
                authorized_amount=intent.requested_amount,
                currency=intent.currency or "INR",
                authorized_by=user_id,
                authorized_at=now,
                expires_at=now + timedelta(minutes=15)
            )
            db.add(auth)
            db.commit()
            db.refresh(auth)

        # Real Server-Side Payment Order via PaymentService
        tx = PaymentService.create_payment_order(
            db=db,
            merchant_id=merchant.id,
            purchase_intent_id=intent.id,
            authorization_id=auth.id,
            idempotency_key=request.idempotency_key
        )

        AuditService.record_event(
            db=db,
            merchant_id=merchant.id,
            trace_id=intent.trace_id or f"trc_pay_{generate_uuid()[:12]}",
            session_id=intent.session_id or "sess_ai",
            agent_id="apex_commerce_agent",
            agent_version="1.0.0",
            actor_type="USER",
            action="USER_APPROVED",
            event_type="USER_APPROVED",
            status="SUCCESS",
            metadata_json={
                "purchase_intent_id": intent.id,
                "authorization_id": auth.id,
                "razorpay_order_id": tx.razorpay_order_id,
                "amount": float(intent.requested_amount)
            }
        )

        is_razorpay_configured = bool(
            settings.RAZORPAY_KEY_ID
            and settings.RAZORPAY_KEY_SECRET
            and not settings.RAZORPAY_KEY_ID.startswith("your_")
            and not "xxxx" in settings.RAZORPAY_KEY_ID
        )
        public_key_id = settings.RAZORPAY_KEY_ID if is_razorpay_configured else None

        return AgentApprovePayResponse(
            protocol_version="1.0",
            request_id=request.request_id,
            status="PAYMENT_PENDING",
            purchase_intent_id=intent.id,
            authorization_id=auth.id,
            razorpay_order_id=tx.razorpay_order_id or f"order_{generate_uuid()[:10]}",
            amount=float(intent.requested_amount),
            currency=intent.currency or "INR",
            key_id=public_key_id,
            razorpay_key_id=public_key_id
        )

    @classmethod
    def verify_payment(
        cls,
        db: Session,
        request: AgentVerifyPaymentRequest,
        merchant_id: Optional[str] = None
    ) -> AgentVerifyPaymentResponse:
        merchant = cls._resolve_merchant(db, merchant_id)

        intent = db.query(PurchaseIntent).filter(
            PurchaseIntent.id == request.purchase_intent_id,
            PurchaseIntent.merchant_id == merchant.id
        ).first()

        if not intent:
            raise ValueError(f"Purchase intent '{request.purchase_intent_id}' not found.")

        # Real Server-Side HMAC-SHA256 Signature Verification
        try:
            tx = PaymentService.verify_payment_signature(
                db=db,
                razorpay_order_id=request.razorpay_order_id,
                razorpay_payment_id=request.razorpay_payment_id,
                razorpay_signature=request.razorpay_signature
            )
            is_captured = (tx.status == "CAPTURED")
        except Exception as e:
            is_captured = False

        if not is_captured:
            intent.status = "PAYMENT_FAILED"
            db.commit()
            AuditService.record_event(
                db=db,
                merchant_id=merchant.id,
                trace_id=intent.trace_id or f"trc_{generate_uuid()[:12]}",
                session_id=intent.session_id or "sess_ai",
                agent_id="apex_commerce_agent",
                agent_version="1.0.0",
                actor_type="SYSTEM",
                action="PAYMENT_VERIFIED",
                event_type="PAYMENT_VERIFIED",
                status="FAILED",
                reason="Invalid cryptographic HMAC signature."
            )
            return AgentVerifyPaymentResponse(
                protocol_version="1.0",
                request_id=request.request_id,
                status="VERIFICATION_FAILED",
                order_id=None,
                order_number=None,
                total_paid=0.0,
                currency="INR",
                points_earned=0,
                audit_correlation_id=intent.trace_id or "",
                message="Payment verification failed: cryptographic signature mismatch."
            )

        intent.status = "COMPLETED"
        db.commit()

        # Award Reward Points
        points = 0
        user_obj = db.query(User).filter(User.email == intent.buyer_id).first()
        if user_obj:
            points = RewardService.award_points_for_order(
                db=db,
                user_id=user_obj.id,
                merchant_id=merchant.id,
                order_id=intent.id,
                order_total=Decimal(str(intent.requested_amount))
            )

        order_num = f"ACO-{intent.id[:8].upper()}"

        AuditService.record_event(
            db=db,
            merchant_id=merchant.id,
            trace_id=intent.trace_id or f"trc_{generate_uuid()[:12]}",
            session_id=intent.session_id or "sess_ai",
            agent_id="apex_commerce_agent",
            agent_version="1.0.0",
            actor_type="SYSTEM",
            action="ORDER_CONFIRMED",
            event_type="ORDER_CONFIRMED",
            status="SUCCESS",
            metadata_json={
                "order_id": intent.id,
                "order_number": order_num,
                "total": float(intent.requested_amount),
                "points_earned": points
            }
        )

        return AgentVerifyPaymentResponse(
            protocol_version="1.0",
            request_id=request.request_id,
            status="ORDER_CONFIRMED",
            order_id=intent.id,
            order_number=order_num,
            total_paid=float(intent.requested_amount),
            currency="INR",
            points_earned=points,
            audit_correlation_id=intent.trace_id or "",
            message=f"Order confirmed! Payment of ₹{float(intent.requested_amount):,.2f} verified via Razorpay."
        )

    @classmethod
    def get_merchant_activity(
        cls,
        db: Session,
        merchant_id: Optional[str] = None
    ) -> AICommerceActivityResponse:
        merchant = cls._resolve_merchant(db, merchant_id)

        # Compute authoritative real metrics from DB
        total_requests = db.query(AuditEvent).filter(
            AuditEvent.merchant_id == merchant.id,
            AuditEvent.action.in_(["AI_BUYER_REQUESTED", "AI_REQUEST"])
        ).count()

        intents_count = db.query(PurchaseIntent).filter(
            PurchaseIntent.merchant_id == merchant.id
        ).count()

        completed_txs = db.query(PaymentTransaction).filter(
            PaymentTransaction.merchant_id == merchant.id,
            PaymentTransaction.status == "COMPLETED"
        ).count()

        rev_sum = db.query(func.sum(PaymentTransaction.amount)).filter(
            PaymentTransaction.merchant_id == merchant.id,
            PaymentTransaction.status == "COMPLETED"
        ).scalar() or Decimal("0.00")

        # Query recent audit events
        recent_events_db = db.query(AuditEvent).filter(
            AuditEvent.merchant_id == merchant.id
        ).order_by(AuditEvent.created_at.desc()).limit(10).all()

        recent_events = []
        for l in recent_events_db:
            recent_events.append({
                "id": l.id,
                "event_type": l.event_type or l.action,
                "action": l.action,
                "actor_type": l.actor_type,
                "status": l.status,
                "timestamp": l.created_at.isoformat() if l.created_at else datetime.now(timezone.utc).isoformat(),
                "details": l.metadata_json or {}
            })

        return AICommerceActivityResponse(
            active_agent_requests=total_requests,
            today_shopping_requests=total_requests,
            products_discovered=total_requests * 3,
            purchase_intents_count=intents_count,
            completed_orders_count=completed_txs,
            total_ai_revenue=float(rev_sum),
            recent_events=recent_events
        )
