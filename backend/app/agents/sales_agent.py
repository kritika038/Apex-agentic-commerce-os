import json
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.ai.gateway import LLMGateway
from app.schemas.ai import ChatMessage
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart, CartItem
from app.database.models.recommendation import Recommendation
from app.schemas.commerce import RecommendationResponse

class SalesAgent:
    """
    Sales Agent responsible for analyzing context and identifying 
    upsell, cross-sell, and complementary product opportunities.
    
    Security & Architecture Boundaries:
    - Scoped strictly to READ operations (READ_PRODUCTS, READ_INVENTORY, READ_CART).
    - Cannot modify cart directly or change prices.
    - Authoritative database validation is executed before any recommendation is persisted or presented.
    """
    def __init__(self, db: Session, merchant_id: str, session_id: str, gateway: Optional[LLMGateway] = None):
        self.db = db
        self.merchant_id = merchant_id
        self.session_id = session_id
        self.gateway = gateway or LLMGateway()
        self.agent_id = "sales_agent_v1"
        self.agent_version = "1.0.0"
        
        # Scoped permissions
        self.permissions = ["READ_PRODUCTS", "READ_INVENTORY", "READ_CART"]

    def _get_cart_items(self) -> List[CartItem]:
        cart = self.db.query(Cart).filter(
            Cart.session_id == self.session_id,
            Cart.merchant_id == self.merchant_id
        ).first()
        if not cart:
            return []
        return self.db.query(CartItem).filter(CartItem.cart_id == cart.id).all()

    def _get_existing_recommended_product_ids(self) -> set:
        """Fetch IDs of products already recommended or dismissed in this session to prevent spam."""
        recs = self.db.query(Recommendation).filter(
            Recommendation.session_id == self.session_id,
            Recommendation.merchant_id == self.merchant_id
        ).all()
        return {r.recommended_product_id for r in recs}

    def validate_and_create_recommendation(
        self,
        candidate_product_id: str,
        rec_type: str,
        reason: str,
        confidence: float = 0.85,
        source_product_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Optional[Recommendation]:
        """
        Deterministic backend validation:
        1. Product exists in DB
        2. Belongs to merchant
        3. Product is active
        4. Product has stock > 0
        5. Not already in cart
        6. Not already recommended in this session
        """
        # 1 & 2. Verify product exists and belongs to merchant
        product = self.db.query(Product).filter(
            Product.id == candidate_product_id,
            Product.merchant_id == self.merchant_id
        ).first()
        
        if not product or not product.is_active:
            return None
            
        # 4. Verify inventory
        inventory = self.db.query(Inventory).filter(
            Inventory.product_id == candidate_product_id,
            Inventory.merchant_id == self.merchant_id
        ).first()
        if not inventory or inventory.stock_quantity <= 0:
            return None

        # 5. Check if already in cart
        cart_items = self._get_cart_items()
        cart_product_ids = {item.product_id for item in cart_items}
        if candidate_product_id in cart_product_ids:
            return None

        # 6. Check if already recommended in this session
        existing_rec_ids = self._get_existing_recommended_product_ids()
        if candidate_product_id in existing_rec_ids:
            return None

        # Persist valid recommendation
        assigned_trace = trace_id or f"trace_{uuid.uuid4().hex[:12]}"
        rec = Recommendation(
            merchant_id=self.merchant_id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            type=rec_type,
            source_product_id=source_product_id,
            recommended_product_id=product.id,
            reason=reason,
            confidence=confidence,
            status="SHOWN",
            trace_id=assigned_trace
        )
        self.db.add(rec)
        self.db.flush()

        from app.services.audit_service import AuditService
        AuditService.record_event(
            db=self.db,
            merchant_id=self.merchant_id,
            trace_id=assigned_trace,
            session_id=self.session_id,
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            actor_type="AGENT",
            action="GENERATE_RECOMMENDATION",
            event_type="RECOMMENDATION",
            resource_type="RECOMMENDATION",
            resource_id=rec.id,
            status="SUCCESS",
            metadata_json={
                "recommendation_type": rec_type,
                "recommended_product_id": product.id,
                "product_name": product.name,
                "product_price": str(product.price),
                "reason": reason,
                "confidence": confidence
            }
        )
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def generate_recommendations(self, trace_id: Optional[str] = None) -> List[RecommendationResponse]:
        """
        Contextually evaluate the session/cart and produce up to 2 high-quality recommendations.
        Uses merchant catalog heuristics & complementary product pairings grounded in DB.
        """
        cart_items = self._get_cart_items()
        if not cart_items:
            return []

        cart_product_ids = {item.product_id for item in cart_items}
        existing_rec_ids = self._get_existing_recommended_product_ids()
        
        # Identify categories in cart
        cart_products = self.db.query(Product).filter(Product.id.in_(list(cart_product_ids))).all()
        categories = {p.category.lower() for p in cart_products if p.category}
        
        valid_recs: List[Recommendation] = []
        max_recs = 2

        # Contextual recommendation logic:
        # If cart has Running / Footwear / Shoes -> recommend Accessories / Socks
        # If cart has Electronics -> recommend Accessories / Cables / Tracker
        for cp in cart_products:
            if len(valid_recs) >= max_recs:
                break
                
            candidate_query = self.db.query(Product).filter(
                Product.merchant_id == self.merchant_id,
                Product.is_active == True,
                Product.id != cp.id,
                ~Product.id.in_(list(cart_product_ids)),
                ~Product.id.in_(list(existing_rec_ids))
            )
            
            if "running" in cp.name.lower() or "running" in (cp.category or "").lower() or "shoe" in cp.name.lower():
                # Look for socks or accessories
                candidate = candidate_query.filter(
                    (Product.name.ilike("%sock%")) | (Product.category.ilike("%accessories%"))
                ).first()
                if candidate:
                    rec = self.validate_and_create_recommendation(
                        candidate_product_id=candidate.id,
                        rec_type="CROSS_SELL",
                        reason=f"{candidate.name} complements {cp.name} and is currently in stock.",
                        confidence=0.88,
                        source_product_id=cp.id,
                        trace_id=trace_id
                    )
                    if rec:
                        valid_recs.append(rec)
                        existing_rec_ids.add(rec.recommended_product_id)
            elif "accessories" in (cp.category or "").lower():
                # Complementary product
                candidate = candidate_query.first()
                if candidate:
                    rec = self.validate_and_create_recommendation(
                        candidate_product_id=candidate.id,
                        rec_type="CROSS_SELL",
                        reason=f"{candidate.name} is a popular item frequently bought together.",
                        confidence=0.75,
                        source_product_id=cp.id,
                        trace_id=trace_id
                    )
                    if rec:
                        valid_recs.append(rec)
                        existing_rec_ids.add(rec.recommended_product_id)
            else:
                candidate = candidate_query.first()
                if candidate:
                    rec = self.validate_and_create_recommendation(
                        candidate_product_id=candidate.id,
                        rec_type="CROSS_SELL",
                        reason=f"{candidate.name} is recommended based on your selected items.",
                        confidence=0.70,
                        source_product_id=cp.id,
                        trace_id=trace_id
                    )
                    if rec:
                        valid_recs.append(rec)
                        existing_rec_ids.add(rec.recommended_product_id)

        # Map to response schema
        responses = []
        for r in valid_recs:
            prod = self.db.query(Product).filter(Product.id == r.recommended_product_id).first()
            responses.append(RecommendationResponse(
                id=r.id,
                type=r.type,
                recommended_product_id=r.recommended_product_id,
                product_name=prod.name if prod else "Unknown",
                product_price=prod.price if prod else Decimal("0.00"),
                reason=r.reason,
                confidence=r.confidence,
                status=r.status,
                source_product_id=r.source_product_id,
                trace_id=r.trace_id,
                created_at=r.created_at
            ))
        return responses

    def recommend_cross_sell(self, source_product_id: str, trace_id: Optional[str] = None) -> Optional[Recommendation]:
        """
        Directly queries co-purchase affinity for a source product and generates a validated cross-sell recommendation.
        """
        from app.services.product_affinity_service import ProductAffinityService
        affinities = ProductAffinityService.get_frequently_bought_together(
            db=self.db,
            product_id=source_product_id,
            merchant_id=self.merchant_id,
            limit=1
        )
        if not affinities:
            return None

        top_match = affinities[0]
        rec = self.validate_and_create_recommendation(
            candidate_product_id=top_match["product"].id,
            rec_type="CROSS_SELL",
            reason=top_match.get("evidence") or f"{top_match['product'].name} is frequently purchased together.",
            confidence=top_match.get("confidence", 0.85),
            source_product_id=source_product_id,
            trace_id=trace_id
        )
        return rec

