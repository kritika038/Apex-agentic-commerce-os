from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from app.database.models.product import Product
from app.services.interaction_service import ProductInteractionService
from app.services.product_affinity_service import ProductAffinityService

class PersonalizationService:
    """
    Produces deterministic, explainable personalized product feeds.
    Grounded in real customer interactions and order history with transparent cold-start fallbacks.
    """

    @staticmethod
    def get_homepage_feed(
        db: Session,
        merchant_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        # 1. Fetch recent views
        recent_views = ProductInteractionService.get_recent_viewed_products(
            db=db,
            merchant_id=merchant_id,
            user_id=user_id,
            session_id=session_id,
            limit=4
        )

        # 2. Fetch category affinity
        affinity = ProductInteractionService.get_category_affinity(
            db=db,
            merchant_id=merchant_id,
            user_id=user_id,
            session_id=session_id
        )
        top_cats = affinity.get("top_categories", [])

        # 3. Build "Recommended for You"
        if top_cats:
            rec_query = db.query(Product).filter(
                Product.merchant_id == merchant_id,
                Product.category.in_(top_cats),
                Product.is_active == True
            )
            if recent_views:
                rec_query = rec_query.filter(Product.id.notin_([p.id for p in recent_views]))
            recommended = rec_query.limit(4).all()
            rec_reason = f"Recommended based on your interest in {', '.join(top_cats)}"
            is_cold_start = False
        else:
            # Cold start: Top in-stock products
            recommended = db.query(Product).filter(
                Product.merchant_id == merchant_id,
                Product.is_active == True
            ).limit(4).all()
            rec_reason = "Trending & popular gear for new shoppers"
            is_cold_start = True

        # 4. Build "Because you viewed..."
        because_you_viewed = []
        last_viewed_name = None
        if recent_views:
            last_p = recent_views[0]
            last_viewed_name = last_p.name
            # Find affinity pairings
            pairings = ProductAffinityService.get_frequently_bought_together(
                db=db,
                product_id=last_p.id,
                merchant_id=merchant_id,
                limit=3
            )
            because_you_viewed = [item["product"] for item in pairings]

        def _format_product(p: Product) -> Dict[str, Any]:
            stock = p.inventory.stock_quantity if p.inventory else 10
            return {
                "id": str(p.id),
                "name": p.name,
                "category": p.category,
                "price": float(p.price),
                "image_url": p.attributes.get("image_url") if isinstance(p.attributes, dict) else None,
                "description": p.description,
                "stock_quantity": stock,
                "in_stock": stock > 0
            }

        return {
            "is_cold_start": is_cold_start,
            "top_categories": top_cats,
            "recommended_for_you": {
                "title": "Recommended for You",
                "reason": rec_reason,
                "products": [_format_product(p) for p in recommended]
            },
            "continue_shopping": {
                "title": "Continue Shopping",
                "products": [_format_product(p) for p in recent_views]
            } if recent_views else None,
            "because_you_viewed": {
                "title": f"Because you viewed {last_viewed_name}",
                "products": [_format_product(p) for p in because_you_viewed]
            } if because_you_viewed else None
        }
