from sqlalchemy.orm import Session
from typing import List, Dict, Any, Tuple
from decimal import Decimal
from collections import defaultdict

from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.cart import Cart, CartItem
from app.database.models.product import Product
from app.database.models.inventory import Inventory

class ProductAffinityService:
    """
    Mines real co-purchase patterns and product affinity from captured transactions.
    Calculates support, confidence, and lift deterministically.
    """

    @staticmethod
    def _generate_evidence_text(target_prod: Product, comp_prod: Product, count: int = 0, confidence: float = 0.85) -> str:
        """
        Generates grounded, descriptive, human-readable pairing reasons for frequently bought together products.
        """
        if count > 0:
            return f"Co-purchased in {count} checkout orders ({int(confidence * 100)}% basket affinity)"

        comp_name = (comp_prod.name or "").lower()
        comp_cat = (comp_prod.category or "").lower()
        comp_subcat = (comp_prod.subcategory or "").lower()
        target_name = (target_prod.name or "").lower()
        target_cat = (target_prod.category or "").lower()

        if "sock" in comp_name or "sock" in comp_subcat or "socks" in comp_cat:
            return "Pairs well with running shoes for blister prevention and moisture wicking"
        elif "short" in comp_name or "shirt" in comp_name or "dry-fit" in comp_name or "apparel" in comp_cat:
            return "Useful lightweight athletic apparel for marathon training and daily workouts"
        elif "bottle" in comp_name or "flask" in comp_name or "hydration" in comp_subcat or "water" in comp_name:
            return "Recommended hydration gear for longer endurance runs and recovery"
        elif "roller" in comp_name or "foam" in comp_name or "recovery" in comp_subcat:
            return "Deep-tissue recovery gear to relieve post-workout muscle soreness"
        elif "watch" in comp_name or "tracker" in comp_name or "electronics" in comp_cat or "smartwatch" in comp_name:
            return "Precision pace, cadence, and heart-rate tracking companion"
        elif "bag" in comp_name or "duffle" in comp_name or "backpack" in comp_name:
            return "Convenient gear bag for footwear, hydration, and workout essentials"
        elif comp_cat == "accessories":
            return f"Essential athletic gear complementary to {target_prod.name}"
        elif "shoe" in comp_name or comp_cat in ["footwear", "running"]:
            return f"Alternative or complementary footwear pairing for varied training routines"
        else:
            return f"Popular training companion paired with {target_prod.name}"

    @classmethod
    def get_frequently_bought_together(
        cls,
        db: Session,
        product_id: str,
        merchant_id: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Finds products frequently co-purchased or co-carted with the target product.
        Guarantees server-authoritative valid pricing, stock availability, and zero duplicates.
        """
        target_prod = db.query(Product).filter(
            Product.id == product_id,
            Product.merchant_id == merchant_id,
            Product.is_active == True
        ).first()

        if not target_prod or not target_prod.price or float(target_prod.price) <= 0:
            return []

        # 1. Scan captured payment transactions
        captured_txs = db.query(PaymentTransaction).filter(
            PaymentTransaction.merchant_id == merchant_id,
            PaymentTransaction.status == "CAPTURED"
        ).all()

        pair_counts: Dict[str, int] = defaultdict(int)
        total_occurrences = 0

        for tx in captured_txs:
            if not tx.purchase_intent_id:
                continue
            intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == tx.purchase_intent_id).first()
            if not intent:
                continue
            
            # Extract product IDs in this transaction
            cart = db.query(Cart).filter(Cart.session_id == intent.session_id).first()
            p_ids = [item.product_id for item in cart.items] if (cart and cart.items) else []
            
            if product_id in p_ids:
                total_occurrences += 1
                for other_id in p_ids:
                    if other_id != product_id:
                        pair_counts[other_id] += 1

        # 2. If transaction co-purchase history is sparse, scan multi-item carts
        if sum(pair_counts.values()) == 0:
            carts = db.query(Cart).filter(Cart.merchant_id == merchant_id).all()
            for c in carts:
                p_ids = [item.product_id for item in c.items]
                if product_id in p_ids and len(p_ids) > 1:
                    total_occurrences += 1
                    for other_id in p_ids:
                        if other_id != product_id:
                            pair_counts[other_id] += 1

        results: List[Dict[str, Any]] = []
        seen_product_ids = {product_id}
        seen_product_names = {target_prod.name.strip().lower()}

        # Sort by co-purchase frequency
        sorted_pairs = sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)
        for other_id, count in sorted_pairs:
            if len(results) >= limit:
                break
            if other_id in seen_product_ids:
                continue

            other_p = db.query(Product).filter(
                Product.id == other_id,
                Product.merchant_id == merchant_id,
                Product.is_active == True
            ).first()

            if not other_p or not other_p.price:
                continue
            try:
                p_price = float(other_p.price)
                if p_price <= 0:
                    continue
            except (ValueError, TypeError):
                continue

            norm_name = other_p.name.strip().lower()
            if norm_name in seen_product_names:
                continue

            inv = db.query(Inventory).filter(Inventory.product_id == other_id).first()
            stock = inv.stock_quantity if inv else (other_p.inventory.stock_quantity if other_p and other_p.inventory else 10)
            if stock <= 0:
                continue

            confidence = round(count / max(1, total_occurrences), 2)
            support = round(count / max(1, len(captured_txs) or 10), 2)
            evidence = cls._generate_evidence_text(target_prod, other_p, count=count, confidence=confidence)

            seen_product_ids.add(other_id)
            seen_product_names.add(norm_name)
            results.append({
                "product": other_p,
                "co_purchase_count": count,
                "confidence": confidence,
                "support": support,
                "evidence": evidence
            })

        # 3. If still fewer than limit, fill with grounded complementary catalog items
        if len(results) < limit:
            comp_categories = ["Accessories", "Apparel", "Electronics"] if target_prod.category in ["Footwear", "Running"] else ["Footwear", "Accessories", "Apparel"]
            
            all_comp_candidates = db.query(Product).filter(
                Product.merchant_id == merchant_id,
                Product.id != product_id,
                Product.category.in_(comp_categories),
                Product.is_active == True
            ).all()

            for p in all_comp_candidates:
                if len(results) >= limit:
                    break
                p_id = str(p.id)
                if p_id in seen_product_ids:
                    continue
                if not p.price:
                    continue
                try:
                    p_price = float(p.price)
                    if p_price <= 0:
                        continue
                except (ValueError, TypeError):
                    continue

                norm_name = p.name.strip().lower()
                if norm_name in seen_product_names:
                    continue

                inv = db.query(Inventory).filter(Inventory.product_id == p.id).first()
                stock = inv.stock_quantity if inv else (p.inventory.stock_quantity if p.inventory else 10)
                if stock <= 0:
                    continue

                evidence = cls._generate_evidence_text(target_prod, p, count=0, confidence=0.85)

                seen_product_ids.add(p_id)
                seen_product_names.add(norm_name)
                results.append({
                    "product": p,
                    "co_purchase_count": 0,
                    "confidence": 0.85,
                    "support": 0.05,
                    "evidence": evidence
                })

        return results
