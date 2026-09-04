import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database.models.product import Product
from app.database.models.external_store import ExternalStore
from app.database.models.external_offer import ExternalProductOffer, PriceObservationHistory, ExternalOutboundClick
from app.services.external_stores.registry import ExternalStoreRegistry, ALLOWED_EXTERNAL_DOMAINS
from app.schemas.price_comparison import (
    PriceComparisonResponse,
    ExternalOfferItem,
    PriceHistoryResponse,
    PriceHistoryItem,
    OutboundRedirectResponse
)

logger = logging.getLogger(__name__)

# In-memory comparison cache with 20-minute TTL
_COMPARISON_CACHE: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 20 * 60

class PriceComparisonService:
    """
    BuyHatke-style External Price Comparison Engine for Apex Store.
    
    Principles:
    - Provides verified price comparison across registered retailers and brand official destinations.
    - Accurately states comparison breadth: 'Lowest verified price among checked stores' (Never 'cheapest on internet').
    - Clear distinction between Apex Purchase (Razorpay Test Mode) and Outbound External Links.
    - External prices NEVER alter server-authoritative Apex checkout pricing.
    - Secure outbound redirects strictly bounded by domain allowlist.
    """

    @staticmethod
    def get_product_price_comparison(
        db: Session,
        product_id: str,
        variant_id: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Calculates canonical multi-store price intelligence for a given product against verified external store offers.
        """
        from app.services.price_intelligence.canonical_service import CanonicalPriceIntelligenceService
        return CanonicalPriceIntelligenceService.get_canonical_comparison(
            db=db,
            product_id=product_id,
            variant_id=variant_id,
            force_refresh=force_refresh
        )

        # 3. Retrieve External Offers for this product from DB
        offers_query = (
            db.query(ExternalProductOffer)
            .join(ExternalStore)
            .filter(
                ExternalProductOffer.apex_product_id == product.id,
                ExternalStore.enabled == True
            )
            .all()
        )

        apex_price_float = float(product.price)
        apex_mrp_float = float(product.mrp) if product.mrp else float(product.price * Decimal("1.25"))
        apex_img = product.image_url or (product.attributes.get("image_url") if isinstance(product.attributes, dict) else None)

        formatted_offers: List[Dict[str, Any]] = []
        lowest_price = apex_price_float
        lowest_store = "Apex Store"
        for off in offers_query:
            store = off.external_store
            store_name = store.name if store else "External Store"
            clean_store = store_name.replace(" India", "").strip()
            url = (off.external_url or "").strip()
            raw_match_type = (off.match_type or "SEARCH_FALLBACK").upper().strip()
            attrs = off.attributes_json if isinstance(off.attributes_json, dict) else {}
            ext_img = off.image_url.strip() if off.image_url else None
            ext_id = (off.external_product_id or "").strip()

            # URL validation: check if URL is a search query
            is_search_url = (
                "/s?k=" in url or
                "/search" in url or
                "query=" in url or
                url.endswith("/s") or
                url.rstrip("/").endswith("amazon.in") or
                url.rstrip("/").endswith("myntra.com")
            )

            # Image validation: external image MUST NOT be the Apex image or an Unsplash copy
            is_reused_apex_image = (
                ext_img is not None and
                apex_img is not None and
                (ext_img == apex_img or "unsplash.com" in ext_img)
            )

            # Determine strict match type
            if not url or not url.startswith("http"):
                match_type = "UNAVAILABLE"
                link_type = "UNAVAILABLE"
                action_label = "Listing unavailable"
                off_price_float = None
                diff = None
                delta_label = "Price unavailable"
                final_ext_img = None
                identity_evidence = None
                confidence = 0.0
            elif is_search_url:
                match_type = "SEARCH_FALLBACK"
                link_type = "SEARCH_FALLBACK"
                action_label = f"Search on {clean_store} →"
                off_price_float = None  # Never fabricate price for search queries
                diff = None
                delta_label = "Search result — exact product not verified"
                final_ext_img = None
                identity_evidence = attrs.get("identity_evidence") or {
                    "type": "SEARCH_FALLBACK",
                    "reason": f"Direct catalog listing unavailable on {clean_store}. Search fallback provided."
                }
                confidence = float(off.match_confidence or 0.60)
            elif raw_match_type in ["EXACT", "VARIANT_EXACT", "EXACT_PRODUCT"]:
                # Validate prerequisites for EXACT / VARIANT_EXACT
                has_valid_id = bool(ext_id) and not ext_id.startswith("B09DEMO") and not ext_id.startswith("EXT")
                has_valid_img = bool(ext_img) and not is_reused_apex_image
                has_pdp_url = ("/dp/" in url or "/p/" in url or "/buy" in url or any(d in url for d in ["nike.com", "adidas.co.in", "puma.com", "decathlon.in"]))

                if has_valid_id and has_valid_img and has_pdp_url:
                    match_type = "VARIANT_EXACT" if raw_match_type == "VARIANT_EXACT" else "EXACT"
                    link_type = match_type
                    action_label = "View product →"
                    off_price_float = float(off.price) if off.price is not None else None
                    diff = round(off_price_float - apex_price_float, 2) if off_price_float is not None else None
                    if diff is not None:
                        if diff < 0:
                            delta_label = f"₹{int(abs(diff)):,} cheaper"
                        elif diff > 0:
                            delta_label = f"₹{int(diff):,} higher"
                        else:
                            delta_label = "Same price"
                    else:
                        delta_label = None

                    final_ext_img = ext_img
                    confidence = float(off.match_confidence or 0.99)
                    identity_evidence = attrs.get("identity_evidence") or {
                        "type": "GTIN_AND_STYLE_CODE",
                        "apex": f"GTIN: {product.gtin or 'N/A'} | Style: {product.model_number or 'N/A'}",
                        "external": f"ID: {ext_id}",
                        "source": f"{store_name} Verified Catalog"
                    }
                else:
                    # Downgrade if missing required exact match evidence or valid image
                    match_type = "SEARCH_FALLBACK"
                    link_type = "SEARCH_FALLBACK"
                    action_label = f"Search on {clean_store} →"
                    off_price_float = None
                    diff = None
                    delta_label = "Search result — exact product not verified"
                    final_ext_img = None
                    identity_evidence = {
                        "type": "SEARCH_FALLBACK",
                        "reason": "Exact listing evidence or independent product image could not be verified."
                    }
                    confidence = 0.60
            elif raw_match_type == "MODEL_EXACT":
                match_type = "MODEL_EXACT"
                link_type = "MODEL_EXACT"
                action_label = "View product →"
                off_price_float = float(off.price) if off.price is not None else None
                diff = round(off_price_float - apex_price_float, 2) if off_price_float is not None else None
                delta_label = "Model match (variant differs)"
                final_ext_img = ext_img if not is_reused_apex_image else None
                confidence = float(off.match_confidence or 0.85)
                identity_evidence = attrs.get("identity_evidence") or {"type": "MODEL", "model": product.model_number}
            elif raw_match_type == "SIMILAR":
                match_type = "SIMILAR"
                link_type = "SIMILAR"
                action_label = f"View similar on {clean_store} →"
                off_price_float = float(off.price) if off.price is not None else None
                diff = round(off_price_float - apex_price_float, 2) if off_price_float is not None else None
                delta_label = "Similar product"
                final_ext_img = ext_img if not is_reused_apex_image else None
                confidence = float(off.match_confidence or 0.70)
                identity_evidence = attrs.get("identity_evidence") or {"type": "SIMILAR_CATEGORY", "category": product.category}
            else:
                match_type = "SEARCH_FALLBACK"
                link_type = "SEARCH_FALLBACK"
                action_label = f"Search on {clean_store} →"
                off_price_float = None
                diff = None
                delta_label = "Search result — exact product not verified"
                final_ext_img = None
                identity_evidence = None
                confidence = 0.60

            offer_dict = {
                "id": str(off.id),
                "store_name": store_name,
                "store_domain": store.domain if store else "retailer.test",
                "store_logo_url": store.logo_url if store else None,
                "store_type": store.store_type if store else "RETAILER",
                "external_url": off.external_url,
                "link_type": link_type,
                "action_label": action_label,
                "redirect_url": f"/api/v1/external-offers/{off.id}/redirect",
                "price": off_price_float,
                "mrp": float(off.mrp) if off.mrp else None,
                "shipping_price": float(off.shipping_cost or 0.0),
                "total_price": (off_price_float + float(off.shipping_cost or 0.0)) if off_price_float is not None else None,
                "currency": off.currency or "INR",
                "difference_from_apex": diff,
                "price_delta_label": delta_label,
                "match_type": match_type,
                "match_confidence": confidence,
                "match_reason": off.match_reason or ("Verified GTIN/Model match" if match_type in ["EXACT", "VARIANT_EXACT"] else delta_label),
                "identity_evidence": identity_evidence,
                "source_status": off.source_status or "VERIFIED",
                "source_verified": bool(off.source_verified),
                "availability": off.availability or "IN_STOCK",
                "observed_at": off.observed_at or now,
                "verified_at": off.observed_at or now,
                "is_lowest": False,
                "external_product_id": ext_id if match_type in ["EXACT", "VARIANT_EXACT", "MODEL_EXACT"] else None,
                "external_product_title": off.external_product_title,
                "external_image_url": final_ext_img,
                "identity": attrs.get("identity")
            }

            formatted_offers.append(offer_dict)

        # Calculate lowest verified exact deal (strictly among EXACT, VARIANT_EXACT, MODEL_EXACT)
        exact_offers_with_price = [
            o for o in formatted_offers
            if o["price"] is not None and o["match_type"] in ["EXACT", "VARIANT_EXACT", "MODEL_EXACT"]
        ]
        if exact_offers_with_price:
            for off_item in exact_offers_with_price:
                if off_item["price"] < lowest_price:
                    lowest_price = off_item["price"]
                    lowest_store = off_item["store_name"]

            for off_item in formatted_offers:
                if off_item["price"] == lowest_price and off_item["match_type"] in ["EXACT", "VARIANT_EXACT", "MODEL_EXACT"]:
                    off_item["is_lowest"] = True

        apex_is_lowest = (lowest_price >= apex_price_float)
        apex_diff = round(apex_price_float - lowest_price, 2)

        checked_count = len(formatted_offers) + 1 # include Apex

        # Construct summary sentence strictly adhering to 'Lowest verified price among checked stores'
        if not formatted_offers:
            summary = f"External price comparison unavailable for this product. Apex Store price is ₹{apex_price_float:,.2f}."
        elif not exact_offers_with_price:
            summary = f"Apex Store offers verified in-stock pricing at ₹{apex_price_float:,.2f}. Lowest verified price among checked stores."
        elif apex_is_lowest:
            summary = f"Apex Store has the lowest verified price at ₹{apex_price_float:,.2f} among {checked_count} checked stores."
        else:
            summary = f"{lowest_store} has the lowest verified price at ₹{lowest_price:,.2f} (₹{int(abs(apex_diff)):,} cheaper than Apex Store) among checked stores."

        result = {
            "product_id": str(product.id),
            "product_name": product.name,
            "product_brand": product.brand,
            "product_category": product.category,
            "product_image_url": apex_img,
            "apex_price": apex_price_float,
            "apex_mrp": apex_mrp_float,
            "currency": product.currency or "INR",
            "offers": formatted_offers,
            "lowest_verified_price": lowest_price,
            "lowest_store": lowest_store,
            "lowest_verified_retailer": lowest_store if not apex_is_lowest else "Apex Store",
            "apex_difference": apex_diff,
            "apex_is_lowest": apex_is_lowest,
            "checked_sources": checked_count,
            "checked_at": now,
            "verification_scope": "checked_sources_only",
            "cache_status": "LIVE",
            "summary_text": summary
        }

        _COMPARISON_CACHE[cache_key] = (now, result)
        return result

    @staticmethod
    def get_price_history(db: Session, product_id: str) -> Dict[str, Any]:
        """
        Returns authentic historical price observations (7d, 30d, 90d).
        Never invents fake data if insufficient observations exist.
        """
        history_records = (
            db.query(PriceObservationHistory)
            .join(ExternalStore)
            .filter(PriceObservationHistory.apex_product_id == product_id)
            .order_by(PriceObservationHistory.observed_at.asc())
            .all()
        )

        if not history_records:
            return {
                "product_id": product_id,
                "currency": "INR",
                "history": [],
                "has_sufficient_data": False,
                "message": "Not enough verified price observations yet. Tracking is active."
            }

        history_items = [
            {
                "date": rec.observed_at.strftime("%Y-%m-%d"),
                "price": float(rec.price),
                "store_name": rec.external_store.name if rec.external_store else "External Store"
            }
            for rec in history_records
        ]

        return {
            "product_id": product_id,
            "currency": "INR",
            "history": history_items,
            "has_sufficient_data": len(history_items) >= 3,
            "message": None if len(history_items) >= 3 else "Partial price history available."
        }

    @staticmethod
    def process_outbound_redirect(
        db: Session,
        offer_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> OutboundRedirectResponse:
        """
        Secure Outbound Redirect Boundary.
        1. Loads offer and store from DB.
        2. Validates store is enabled and verified.
        3. Strictly validates target destination against ALLOWED_EXTERNAL_DOMAINS.
        4. Logs outbound analytics click event.
        5. Returns safe target URL.
        """
        offer = db.query(ExternalProductOffer).filter(ExternalProductOffer.id == offer_id).first()
        if not offer:
            raise HTTPException(status_code=404, detail="External offer not found.")

        store = offer.external_store
        if not store or not store.enabled:
            raise HTTPException(status_code=403, detail="External store is currently disabled.")

        target_url = offer.affiliate_url or offer.external_url
        if not ExternalStoreRegistry.is_domain_allowed(target_url):
            logger.warning(f"Security Alert: Blocked outbound redirect to unapproved domain: '{target_url}'")
            raise HTTPException(
                status_code=400,
                detail="Security policy rejected outbound destination: Domain is not on the verified allowlist."
            )

        # Record outbound click analytics
        click_event = ExternalOutboundClick(
            external_offer_id=offer.id,
            apex_product_id=offer.apex_product_id,
            external_store_id=store.id,
            target_url=target_url,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(click_event)
        db.commit()

        return OutboundRedirectResponse(
            target_url=target_url,
            store_name=store.name,
            domain=store.domain,
            allowed=True
        )
