import uuid
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart, CartItem
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.approval_request import ApprovalRequest
from app.database.models.policy_evaluation import PolicyEvaluation

from app.agents.shopping_agent import ShoppingAgent
from app.agents.sales_agent import SalesAgent
from app.services.purchase_intent_service import PurchaseIntentService
from app.policies.policy_engine import PolicyEngine
from app.payments.service import PaymentService
from app.services.audit_service import AuditService

from app.protocol.schemas import (
    ProtocolCapabilitiesResponse,
    ProtocolDiscoverRequest,
    ProtocolDiscoverResponse,
    ProtocolProductItem,
    ProtocolRecommendRequest,
    ProtocolRecommendResponse,
    ProtocolRecommendationItem,
    ProtocolPurchaseIntentRequest,
    ProtocolPurchaseIntentResponse,
    ProtocolAuthorizationStatusResponse,
    ProtocolPaymentRequest,
    ProtocolPaymentResponse
)

class ProtocolService:
    @staticmethod
    def get_capabilities(db: Session, merchant_id: str) -> ProtocolCapabilitiesResponse:
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not merchant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Merchant '{merchant_id}' not found."
            )

        return ProtocolCapabilitiesResponse(
            protocol_version="1.0.0",
            merchant_id=merchant.id,
            merchant_name=merchant.name,
            supported_currency="INR"
        )

    @staticmethod
    def discover(db: Session, req: ProtocolDiscoverRequest, merchant_id: str) -> ProtocolDiscoverResponse:
        trace_id = req.trace_id or f"trc_proto_{uuid.uuid4().hex[:10]}"
        session_id = req.session_id or f"sess_proto_{uuid.uuid4().hex[:8]}"

        # Record Protocol Inbound Event
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=trace_id,
            session_id=session_id,
            actor_type="AGENT",
            actor_id="ExternalAIBuyer",
            action="PROTOCOL_DISCOVER",
            event_type="DISCOVERY",
            status="SUCCESS",
            metadata_json={
                "query": req.query,
                "category": req.category,
                "max_price": str(req.max_price) if req.max_price else None,
                "currency": req.currency
            }
        )

        # Ground query directly against authoritative SQL catalog
        query = db.query(Product).filter(
            Product.merchant_id == merchant_id,
            Product.is_active == True
        )

        if req.category:
            query = query.filter(Product.category.ilike(f"%{req.category}%"))
        if req.max_price is not None:
            query = query.filter(Product.price <= req.max_price)
        if req.query:
            kw = req.query.strip()
            query = query.filter(
                (Product.name.ilike(f"%{kw}%")) |
                (Product.category.ilike(f"%{kw}%")) |
                (Product.description.ilike(f"%{kw}%"))
            )

        products = query.limit(20).all()

        product_items: List[ProtocolProductItem] = []
        for p in products:
            stock = p.inventory.stock_quantity if p.inventory else 0
            product_items.append(ProtocolProductItem(
                id=p.id,
                name=p.name,
                category=p.category or "General",
                price=p.price,
                currency="INR",
                in_stock=stock > 0,
                stock_quantity=stock,
                description=p.description
            ))

        # Retrieve cart context if session exists
        cart = db.query(Cart).filter(
            Cart.merchant_id == merchant_id,
            Cart.session_id == session_id
        ).first()

        cart_items: List[Dict[str, Any]] = []
        if cart and cart.items:
            for it in cart.items:
                p_it = db.query(Product).filter(Product.id == it.product_id).first()
                if p_it:
                    cart_items.append({
                        "product_id": p_it.id,
                        "name": p_it.name,
                        "unit_price": str(p_it.price),
                        "quantity": it.quantity,
                        "subtotal": str(p_it.price * it.quantity)
                    })

        return ProtocolDiscoverResponse(
            session_id=session_id,
            trace_id=trace_id,
            products=product_items,
            total_found=len(product_items),
            cart=cart_items,
            message=f"Discovered {len(product_items)} product(s) matching machine constraints."
        )

    @staticmethod
    def recommend(db: Session, req: ProtocolRecommendRequest, merchant_id: str) -> ProtocolRecommendResponse:
        trace_id = req.trace_id or f"trc_proto_{uuid.uuid4().hex[:10]}"

        # Reuse SalesAgent for grounded merchant cross-sell
        sales_agent = SalesAgent(
            db=db,
            merchant_id=merchant_id,
            session_id=req.session_id
        )

        recs = sales_agent.generate_recommendations(trace_id=trace_id)

        rec_items: List[ProtocolRecommendationItem] = []
        for r in recs:
            rec_items.append(ProtocolRecommendationItem(
                recommendation_id=r.id,
                type=r.type,
                recommended_product_id=r.recommended_product_id,
                product_name=r.product_name,
                product_price=r.product_price,
                currency="INR",
                reason=r.reason,
                confidence=r.confidence,
                status=r.status
            ))

        if not rec_items:
            from app.database.models.recommendation import Recommendation
            existing_recs = db.query(Recommendation).filter(
                Recommendation.merchant_id == merchant_id,
                Recommendation.session_id == req.session_id
            ).all()
            for er in existing_recs:
                p_name = er.product.name if er.product else "Recommended Product"
                p_price = er.product.price if er.product else Decimal("0.00")
                rec_items.append(ProtocolRecommendationItem(
                    recommendation_id=er.id,
                    type=er.type,
                    recommended_product_id=er.recommended_product_id,
                    product_name=p_name,
                    product_price=p_price,
                    currency="INR",
                    reason=er.reason,
                    confidence=er.confidence,
                    status=er.status
                ))

        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=trace_id,
            session_id=req.session_id,
            actor_type="AGENT",
            actor_id="SalesAgent",
            action="PROTOCOL_RECOMMEND",
            event_type="RECOMMENDATION",
            status="SUCCESS",
            metadata_json={
                "recommendations_count": len(rec_items)
            }
        )

        return ProtocolRecommendResponse(
            session_id=req.session_id,
            trace_id=trace_id,
            recommendations=rec_items
        )

    @staticmethod
    def create_purchase_intent(db: Session, req: ProtocolPurchaseIntentRequest, merchant_id: str) -> ProtocolPurchaseIntentResponse:
        trace_id = req.trace_id or f"trc_proto_{uuid.uuid4().hex[:10]}"

        intent = PurchaseIntentService.create_purchase_intent(
            db=db,
            merchant_id=merchant_id,
            session_id=req.session_id,
            buyer_id=req.buyer_id,
            constraints=req.constraints,
            trace_id=trace_id
        )

        # Format items payload from product_summary
        items_payload = intent.product_summary.get("items", []) if intent.product_summary else []

        return ProtocolPurchaseIntentResponse(
            purchase_intent_id=intent.id,
            merchant_id=intent.merchant_id,
            buyer_id=intent.buyer_id,
            cart_id=intent.cart_id,
            status=intent.status,
            requested_amount=intent.requested_amount,
            currency=intent.currency,
            items=items_payload,
            expires_at=intent.expires_at,
            trace_id=trace_id
        )

    @staticmethod
    def get_authorization_status(db: Session, purchase_intent_id: str, merchant_id: str) -> ProtocolAuthorizationStatusResponse:
        intent = db.query(PurchaseIntent).filter(
            PurchaseIntent.id == purchase_intent_id,
            PurchaseIntent.merchant_id == merchant_id
        ).first()

        if not intent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase Intent '{purchase_intent_id}' not found for merchant."
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Check existing TransactionAuthorization
        auth = db.query(TransactionAuthorization).filter(
            TransactionAuthorization.purchase_intent_id == purchase_intent_id,
            TransactionAuthorization.merchant_id == merchant_id
        ).first()

        if auth:
            if auth.status == "AUTHORIZED" and auth.expires_at and now > auth.expires_at:
                auth.status = "EXPIRED"
                db.commit()

            return ProtocolAuthorizationStatusResponse(
                purchase_intent_id=intent.id,
                merchant_id=intent.merchant_id,
                status=auth.status,
                authorization_id=auth.id,
                authorized_amount=auth.authorized_amount,
                currency=auth.currency,
                expires_at=auth.expires_at,
                trace_id=intent.trace_id
            )

        # Check pending ApprovalRequest
        appr = db.query(ApprovalRequest).filter(
            ApprovalRequest.purchase_intent_id == purchase_intent_id,
            ApprovalRequest.merchant_id == merchant_id
        ).first()

        if appr:
            return ProtocolAuthorizationStatusResponse(
                purchase_intent_id=intent.id,
                merchant_id=intent.merchant_id,
                status="REQUIRES_APPROVAL" if appr.status == "PENDING" else appr.status,
                approval_request_id=appr.id,
                risk_level=appr.risk_level,
                authorized_amount=appr.amount,
                currency=appr.currency,
                expires_at=appr.expires_at,
                trace_id=intent.trace_id
            )

        # Check PolicyEvaluation
        eval_record = db.query(PolicyEvaluation).filter(
            PolicyEvaluation.purchase_intent_id == purchase_intent_id,
            PolicyEvaluation.merchant_id == merchant_id
        ).first()

        if eval_record:
            return ProtocolAuthorizationStatusResponse(
                purchase_intent_id=intent.id,
                merchant_id=intent.merchant_id,
                status="DENIED" if eval_record.decision == "DENY" else eval_record.decision,
                risk_level=eval_record.risk_level,
                decision=eval_record.decision,
                trace_id=intent.trace_id
            )

        return ProtocolAuthorizationStatusResponse(
            purchase_intent_id=intent.id,
            merchant_id=intent.merchant_id,
            status="NOT_EVALUATED",
            trace_id=intent.trace_id
        )

    @staticmethod
    def request_payment(db: Session, req: ProtocolPaymentRequest, merchant_id: str) -> ProtocolPaymentResponse:
        trace_id = req.trace_id or f"trc_proto_{uuid.uuid4().hex[:10]}"

        # Strictly derive amount and currency from TransactionAuthorization via PaymentService
        tx = PaymentService.create_payment_order(
            db=db,
            merchant_id=merchant_id,
            purchase_intent_id=req.purchase_intent_id,
            authorization_id=req.authorization_id,
            idempotency_key=req.idempotency_key,
            trace_id=trace_id
        )

        return ProtocolPaymentResponse(
            payment_transaction_id=tx.id,
            razorpay_order_id=tx.razorpay_order_id,
            amount=tx.amount,
            currency=tx.currency,
            status=tx.status,
            receipt=tx.receipt,
            trace_id=trace_id,
            created_at=tx.created_at
        )
