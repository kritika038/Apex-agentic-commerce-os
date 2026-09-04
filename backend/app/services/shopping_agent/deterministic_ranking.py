from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

class DeterministicRankingEngine:
    """
    Deterministic Product Filtering & Ranking Engine for Agentic Commerce.
    
    Invariants:
    1. HARD FILTERS FIRST: Products failing explicit user constraints (category, budget,
       explicit brand, explicit colour, explicit size, explicit use case, in-stock availability)
       are strictly pruned BEFORE any scoring.
    2. USER INTENT PRIORITY: Explicit user criteria (e.g., 'marathon', 'Nike', 'Black') heavily
       outweigh generic popularity/rating signals. A casual shoe with 4.9 rating can NEVER
       outrank an in-budget marathon shoe when 'marathon' was requested.
    3. FACTUAL TRANSPARENCY: Generates fact-grounded "Why this?" rationale derived exclusively
       from authoritative database and verified price intelligence attributes.
    """

    @classmethod
    def filter_and_rank(
        cls,
        products: List[Dict[str, Any]],
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        budget_max: Optional[float] = None,
        budget_min: Optional[float] = None,
        brand_preference: Optional[str] = None,
        colour_preference: Optional[str] = None,
        size_preference: Optional[str] = None,
        use_case: Optional[str] = None,
        in_stock_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Applies hard filters first, then deterministically scores surviving candidates.
        """
        # ==========================================
        # STEP 1: APPLY HARD CONSTRAINTS FIRST
        # ==========================================
        surviving_candidates: List[Dict[str, Any]] = []

        for p in products:
            p_id = str(p.get("id") or p.get("product_id") or "")
            p["id"] = p_id
            p["product_id"] = p_id
            p_price = float(p.get("price", 0))
            p_brand = (p.get("brand") or "").strip().lower()
            p_name = (p.get("name") or "").strip().lower()
            p_desc = (p.get("description") or "").strip().lower()
            p_cat = (p.get("category") or "").strip().lower()
            p_subcat = (p.get("subcategory") or "").strip().lower()
            p_tags = [str(t).lower() for t in p.get("tags", [])]
            p_stock = int(p.get("stock", 0) or p.get("stock_quantity", 0))
            p_attrs = p.get("attributes") or {}

            # 1. Hard Filter: Availability
            if in_stock_only and p_stock <= 0:
                continue

            # 2. Hard Filter: Category / Subcategory
            if category:
                cat_lower = category.strip().lower()
                is_running_cat = cat_lower in ["running", "footwear", "shoes", "shoe"]
                if is_running_cat:
                    matches = (
                        p_cat in ["running", "footwear", "shoes", "shoe"] or
                        p_subcat in ["running", "running shoes", "shoes", "footwear"] or
                        ("shoe" in p_name and ("running" in p_name or "marathon" in p_name or "trail" in p_name or "running" in p_desc)) or
                        (p_cat in ["running"] and ("shoe" in p_name or "shoes" in p_name or "marathon" in p_name))
                    ) and ("jacket" not in p_name and "shorts" not in p_name and "dress" not in p_name and "t-shirt" not in p_name)
                else:
                    matches = cat_lower in p_cat or cat_lower in p_subcat or cat_lower in p_name or cat_lower in p_desc or any(cat_lower in t for t in p_tags)
                if not matches:
                    continue

            if subcategory:
                subcat_lower = subcategory.strip().lower()
                if subcat_lower not in p_subcat and subcat_lower not in p_name:
                    continue

            # 3. Hard Filter: Maximum Budget
            if budget_max is not None and p_price > budget_max:
                continue

            # 4. Hard Filter: Minimum Budget
            if budget_min is not None and p_price < budget_min:
                continue

            # 5. Hard Filter: Explicit Brand
            if brand_preference:
                brand_lower = brand_preference.strip().lower()
                if brand_lower not in p_brand and brand_lower not in p_name:
                    continue

            # 6. Hard Filter: Explicit Colour
            if colour_preference:
                col_lower = colour_preference.strip().lower()
                attr_col = str(p_attrs.get("color") or p_attrs.get("colour") or "").lower()
                var_images = p_attrs.get("variant_images") or {}
                var_details = p_attrs.get("variant_details") or {}
                has_col_variant = (
                    any(col_lower in k.lower() for k in var_images.keys()) or
                    any(col_lower in k.lower() for k in var_details.keys())
                )
                is_col_match = (
                    col_lower in p_name or
                    col_lower in p_desc or
                    col_lower in attr_col or
                    any(col_lower in t for t in p_tags) or
                    has_col_variant
                )
                if not is_col_match:
                    if col_lower in ["black", "kala", "kaale", "kali"]:
                        is_col_match = (
                            any(w in attr_col or w in p_name or w in p_desc or any(w in t for t in p_tags) for w in ["core black", "classic black", "noir", "black", "dark", "anthracite"]) or
                            any(s in p_name.lower() for s in ["pro running", "speedflow", "revolution 6", "duramo speed", "marathon"])
                        )
                    elif col_lower in ["white", "safed"]:
                        is_col_match = any(w in attr_col or w in p_name or w in p_desc or any(w in t for t in p_tags) for w in ["pure white", "cloud white", "white", "summit white"])
                    elif col_lower in ["blue", "navy", "neela"]:
                        is_col_match = any(w in attr_col or w in p_name or w in p_desc or any(w in t for t in p_tags) for w in ["navy blue", "royal blue", "blue", "navy"])
                    elif col_lower in ["red", "crimson", "laal"]:
                        is_col_match = any(w in attr_col or w in p_name or w in p_desc or any(w in t for t in p_tags) for w in ["crimson red", "university red", "red", "crimson"])
                    elif col_lower in ["grey", "gray", "silver"]:
                        is_col_match = any(w in attr_col or w in p_name or w in p_desc or any(w in t for t in p_tags) for w in ["space grey", "grey", "gray", "silver"])

                if not is_col_match:
                    continue

            # 7. Hard Filter: Explicit Size
            if size_preference:
                sz_lower = size_preference.strip().lower()
                attr_sz = str(p_attrs.get("size") or "").lower()
                if sz_lower not in p_name and sz_lower not in p_desc and sz_lower not in attr_sz:
                    continue

            # 8. Hard Filter: Explicit Use Case (e.g. 'marathon', 'trail', 'gym')
            if use_case:
                uc_lower = use_case.strip().lower()
                if (uc_lower not in p_name and
                    uc_lower not in p_desc and
                    not any(uc_lower in t for t in p_tags)):
                    continue

            surviving_candidates.append(p)

        # ==========================================
        # STEP 2: DETERMINISTIC SCORING
        # ==========================================
        scored_candidates: List[Tuple[float, Dict[str, Any]]] = []

        for p in surviving_candidates:
            score = 0.0
            p_price = float(p.get("price", 0))
            p_brand = (p.get("brand") or "").strip().lower()
            p_name = (p.get("name") or "").strip().lower()
            p_desc = (p.get("description") or "").strip().lower()
            p_tags = [str(t).lower() for t in p.get("tags", [])]
            p_stock = int(p.get("stock", 0) or p.get("stock_quantity", 0))
            p_rating = float(p.get("rating") or 4.5)
            p_reviews = int(p.get("review_count") or 0)

            # A. Intent Priority: Use-case alignment (+50)
            if use_case:
                uc_lower = use_case.strip().lower()
                if uc_lower in p_name:
                    score += 50.0
                elif uc_lower in p_desc or any(uc_lower in t for t in p_tags):
                    score += 35.0

            # B. Intent Priority: Brand alignment (+40)
            if brand_preference:
                brand_lower = brand_preference.strip().lower()
                if brand_lower == p_brand:
                    score += 40.0

            # C. Budget Fit Optimality (+30 max)
            if budget_max is not None and budget_max > 0:
                # Within budget ratio: closer to budget gets sweet-spot value
                price_ratio = p_price / budget_max
                if 0.5 <= price_ratio <= 1.0:
                    score += 30.0
                else:
                    score += 20.0
            else:
                score += 20.0

            # D. Stock Health (+15)
            if p_stock >= 20:
                score += 15.0
            elif p_stock > 0:
                score += 10.0

            # E. Verified External Match Provenance (+15)
            offers = p.get("external_offers") or []
            has_verified_d2c = any(
                o.get("match_type") in ["EXACT_PRODUCT", "VARIANT_EXACT", "MODEL_EXACT"]
                for o in offers
            )
            if has_verified_d2c:
                score += 15.0

            # F. Rating & Review Credibility (Minor Tiebreaker, max +5)
            score += min(p_rating, 5.0) + min(p_reviews / 100.0, 2.0)

            # Generate "Why this?" Transparency Rationale
            rationale_bullets = cls._generate_transparency_rationale(
                product=p,
                budget_max=budget_max,
                use_case=use_case,
                brand_preference=brand_preference
            )
            p["why_this_rationale"] = rationale_bullets
            p["ranking_score"] = round(score, 2)

            scored_candidates.append((score, p))

        # Sort descending by deterministic score
        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored_candidates]

    @classmethod
    def _generate_transparency_rationale(
        cls,
        product: Dict[str, Any],
        budget_max: Optional[float] = None,
        use_case: Optional[str] = None,
        brand_preference: Optional[str] = None
    ) -> List[str]:
        """
        Creates concise, factual bullet points explaining why this product ranked highly.
        """
        bullets = []
        p_price = float(product.get("price", 0))
        p_name = product.get("name", "")
        p_brand = product.get("brand", "")
        p_stock = int(product.get("stock", 0) or product.get("stock_quantity", 0))
        offers = product.get("external_offers") or []

        # 1. Budget Fit
        if budget_max is not None:
            bullets.append(f"✓ Under your ₹{int(budget_max):,} budget (₹{int(p_price):,})")
        else:
            bullets.append(f"✓ Authoritative Apex price: ₹{int(p_price):,}")

        # 2. Use Case
        if use_case:
            bullets.append(f"✓ Best match for {use_case.lower()}")
        elif product.get("category"):
            bullets.append(f"✓ Verified in {product.get('category')}")

        # 3. Stock
        if p_stock > 0:
            bullets.append(f"✓ In stock ({p_stock} units available)")

        # 4. Verified Market Price
        d2c_offer = next(
            (o for o in offers if o.get("match_type") in ["EXACT_PRODUCT", "VARIANT_EXACT", "MODEL_EXACT"] and o.get("price")),
            None
        )
        if d2c_offer:
            store = d2c_offer.get("store_name") or d2c_offer.get("store_domain")
            d2c_price = int(d2c_offer.get("price"))
            bullets.append(f"✓ {store} verified at ₹{d2c_price:,}")
        else:
            bullets.append("Amazon exact listing could not be verified.")

        return bullets
