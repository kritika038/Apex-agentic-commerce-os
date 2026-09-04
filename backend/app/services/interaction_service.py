from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from collections import Counter

from app.database.models.product_interaction import ProductInteraction
from app.database.models.product import Product

class ProductInteractionService:
    """
    Records and queries real customer interaction signals (PRODUCT_VIEW, SEARCH, ADD_TO_CART, PURCHASE).
    Enforces privacy, tenant-isolation, and fast preference calculation.
    """

    @staticmethod
    def record_interaction(
        db: Session,
        merchant_id: str,
        product_id: str,
        event_type: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProductInteraction:
        interaction = ProductInteraction(
            merchant_id=merchant_id,
            product_id=product_id,
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            metadata_json=metadata or {}
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        return interaction

    @staticmethod
    def get_recent_viewed_products(
        db: Session,
        merchant_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 6
    ) -> List[Product]:
        q = db.query(ProductInteraction).filter(
            ProductInteraction.merchant_id == merchant_id,
            ProductInteraction.event_type.in_(["PRODUCT_VIEW", "ADD_TO_CART"])
        )
        if user_id:
            q = q.filter(ProductInteraction.user_id == user_id)
        elif session_id:
            q = q.filter(ProductInteraction.session_id == session_id)
        else:
            return []

        interactions = q.order_by(ProductInteraction.created_at.desc()).limit(30).all()
        seen_ids = set()
        product_ids = []
        for i in interactions:
            if i.product_id not in seen_ids:
                seen_ids.add(i.product_id)
                product_ids.append(i.product_id)

        if not product_ids:
            return []

        products = db.query(Product).filter(
            Product.id.in_(product_ids[:limit]),
            Product.is_active == True
        ).all()
        # Preserve recency order
        id_map = {p.id: p for p in products}
        return [id_map[pid] for pid in product_ids[:limit] if pid in id_map]

    @staticmethod
    def get_category_affinity(
        db: Session,
        merchant_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculates category affinity distribution and average viewed price bounds.
        """
        q = db.query(ProductInteraction).filter(ProductInteraction.merchant_id == merchant_id)
        if user_id:
            q = q.filter(ProductInteraction.user_id == user_id)
        elif session_id:
            q = q.filter(ProductInteraction.session_id == session_id)
        else:
            return {"top_categories": [], "avg_price": None, "interaction_count": 0}

        interactions = q.order_by(ProductInteraction.created_at.desc()).limit(50).all()
        if not interactions:
            return {"top_categories": [], "avg_price": None, "interaction_count": 0}

        prod_ids = [i.product_id for i in interactions]
        products = db.query(Product).filter(Product.id.in_(prod_ids)).all()
        prod_map = {p.id: p for p in products}

        categories = []
        prices = []
        for i in interactions:
            p = prod_map.get(i.product_id)
            if p:
                categories.append(p.category)
                prices.append(float(p.price))

        cat_counts = Counter(categories)
        top_cats = [cat for cat, _ in cat_counts.most_common(3)]
        avg_price = (sum(prices) / len(prices)) if prices else None

        return {
            "top_categories": top_cats,
            "avg_price": avg_price,
            "interaction_count": len(interactions)
        }
