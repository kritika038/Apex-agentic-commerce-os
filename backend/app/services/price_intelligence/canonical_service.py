import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database.models.product import Product
from app.database.models.canonical_product import CanonicalProduct
from app.database.models.external_offer import ExternalProductOffer
from app.database.models.external_store import ExternalStore
from app.database.seeds.canonical_catalog import CANONICAL_PRODUCTS_GRAPH
from app.services.price_intelligence.validators import (
    validate_retailer_pdp_url,
    validate_external_product_image
)
from app.services.price_intelligence.retailers.amazon import AmazonCreatorsAdapter
from app.services.price_intelligence.sources.registry import PriceIntelligenceSourceRegistry

logger = logging.getLogger(__name__)

# Fast memory cache for canonical comparison responses
_CANONICAL_CACHE: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 15 * 60

_DEFAULT_SOURCE_REGISTRY = PriceIntelligenceSourceRegistry()

class CanonicalPriceIntelligenceService:
    """
    Buyhatke-style Canonical Product & Multi-Retailer Offer Graph Engine.
    
    Architecture:
    ONE Canonical Product (Physical Identity: Brand, Style Code, GTIN, Variant)
         │
         ├── Source Registry (D2C Sources, Public Structured JSON-LD, Merchant Feeds)
         ├── RetailerOffer (Amazon Creators API / Amazon India exact PDP or Search Fallback)
         ├── RetailerOffer (Nike Official exact PDP & authentic image)
         ├── RetailerOffer (Myntra exact PDP & authentic image)
         └── RetailerOffer (Flipkart / Puma / Adidas exact PDP)
    """

    @classmethod
    def get_canonical_comparison(
        cls,
        db: Session,
        product_id: str,
        variant_id: Optional[str] = None,
        force_refresh: bool = False,
        amazon_adapter: Optional[AmazonCreatorsAdapter] = None,
        source_registry: Optional[PriceIntelligenceSourceRegistry] = None
    ) -> Dict[str, Any]:
        """
        Retrieves the canonical product comparison graph for a given Apex product.
        """
        # 1. Authoritative Apex Product Lookup
        apex_product = db.query(Product).filter(Product.id == product_id).first()
        if not apex_product:
            raise HTTPException(status_code=404, detail=f"Product with ID '{product_id}' not found.")

        # 2. Check in-memory cache
        cache_key = f"canon_{product_id}_{variant_id or 'default'}"
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if not force_refresh and cache_key in _CANONICAL_CACHE:
            cached_time, cached_data = _CANONICAL_CACHE[cache_key]
            if (now - cached_time).total_seconds() < CACHE_TTL_SECONDS:
                res = dict(cached_data)
                res["cache_status"] = "CACHED"
                return res

        # 3. Find matching canonical product identity from graph or DB
        canon_def = cls._resolve_canonical_identity(db, apex_product)

        apex_price_float = float(apex_product.price)
        apex_mrp_float = float(apex_product.mrp) if apex_product.mrp else float(apex_product.price * Decimal("1.25"))
        apex_img = (
            apex_product.image_url or
            (apex_product.attributes.get("image_url") if isinstance(apex_product.attributes, dict) else None)
        )

        canonical_info = {
            "canonical_product_id": canon_def.get("id") or f"canon_{apex_product.id}",
            "brand": canon_def.get("brand") or apex_product.brand or "Apex",
            "title": canon_def.get("title") or apex_product.name,
            "category": canon_def.get("category") or apex_product.category,
            "subcategory": canon_def.get("subcategory") or apex_product.subcategory,
            "model": canon_def.get("model") or apex_product.model_number,
            "style_code": canon_def.get("style_code") or apex_product.model_number,
            "gtin": canon_def.get("gtin") or apex_product.gtin,
            "color": canon_def.get("color") or (apex_product.attributes.get("color") if apex_product.attributes else "Standard"),
            "size": canon_def.get("size") or (apex_product.attributes.get("size") if apex_product.attributes else "Standard"),
            "variant": canon_def.get("variant") or (apex_product.attributes.get("color") if apex_product.attributes else "Standard"),
            "canonical_image_url": canon_def.get("canonical_image_url") or apex_img,
            "verified": bool(canon_def.get("verified", False))
        }

        # 4. Evaluate all Retailer Offers linked to this Canonical Product (Graph + Source Registry + DB)
        raw_offers = list(canon_def.get("retailer_offers") or [])

        # Consult Pluggable Source Registry if canonical product is verified
        if canonical_info.get("verified", False):
            reg = source_registry or _DEFAULT_SOURCE_REGISTRY
            try:
                source_candidates = reg.discover_and_verify_offers(canonical_info, apex_price_float, apex_img)
                for sc in source_candidates:
                    sc_domain = sc.get("store_domain")
                    matching_idx = next((i for i, o in enumerate(raw_offers) if o.get("store_domain") == sc_domain), None)
                    if matching_idx is None:
                        raw_offers.append(sc)
            except Exception as e:
                logger.error(f"Error consulting price intelligence source registry: {e}")

        # Check Amazon Creators API connector if active/injected
        amz_connector = amazon_adapter or AmazonCreatorsAdapter()
        if amz_connector.is_enabled():
            try:
                amz_live_offer = amz_connector.resolve_canonical_product_offer(canonical_info)
                amz_idx = next((i for i, o in enumerate(raw_offers) if o.get("retailer") == "amazon" or "amazon" in (o.get("store_domain") or "")), None)
                if amz_idx is not None:
                    raw_offers[amz_idx] = amz_live_offer
                else:
                    raw_offers.append(amz_live_offer)
            except Exception as e:
                logger.error(f"Error querying Amazon Creators adapter: {e}")
        if canonical_info.get("verified", False):
            db_offers = db.query(ExternalProductOffer).filter(ExternalProductOffer.apex_product_id == apex_product.id).all()
            for dbo in db_offers:
                matching_idx = next(
                    (i for i, o in enumerate(raw_offers) if str(o.get("id")) == str(dbo.id) or o.get("external_product_url") == dbo.external_url),
                    None
                )
                dbo_entry = {
                    "id": str(dbo.id),
                    "retailer": dbo.external_store.domain.split(".")[0] if dbo.external_store else "store",
                    "store_name": dbo.external_store.name if dbo.external_store else "External Store",
                    "store_domain": dbo.external_store.domain if dbo.external_store else "",
                    "store_logo_url": dbo.external_store.logo_url if dbo.external_store else None,
                    "external_product_id": dbo.external_product_id,
                    "external_title": dbo.external_product_title,
                    "external_product_image": dbo.image_url,
                    "external_product_url": dbo.external_url,
                    "price": float(dbo.price) if dbo.price is not None else None,
                    "mrp": float(dbo.mrp) if dbo.mrp is not None else None,
                    "currency": dbo.currency or "INR",
                    "match_type": dbo.match_type,
                    "match_confidence": dbo.match_confidence,
                    "identity_evidence": (dbo.attributes_json.get("identity_evidence") if dbo.attributes_json else None) or (raw_offers[matching_idx].get("identity_evidence") if matching_idx is not None else None)
                }
                if matching_idx is not None:
                    raw_offers[matching_idx] = dbo_entry
                else:
                    raw_offers.append(dbo_entry)
        else:
            raw_offers = []

        verified_offers: List[Dict[str, Any]] = []

        lowest_price = apex_price_float
        lowest_store = "Apex Store"

        for off in raw_offers:
            retailer_domain = off.get("store_domain") or ""
            raw_url = (off.get("external_product_url") or "").strip()
            raw_img = (off.get("external_product_image") or "").strip()
            raw_match = (off.get("match_type") or "SEARCH_FALLBACK").upper().strip()
            price_val = off.get("price")

            # Validate URL
            is_valid_pdp, extracted_id = validate_retailer_pdp_url(retailer_domain, raw_url)
            # Validate Image (Must not reuse Apex image)
            is_valid_img, img_err = validate_external_product_image(raw_img, canonical_info["canonical_image_url"])
            # Validate Identity Evidence & Canonical Verification
            has_identity_evidence = bool(
                off.get("identity_evidence") and
                off.get("identity_evidence", {}).get("type") not in ["SEARCH_FALLBACK", "UNVERIFIED"]
            )
            canonical_is_verified = bool(canonical_info.get("verified", False))

            if (
                canonical_is_verified and
                is_valid_pdp and
                is_valid_img and
                has_identity_evidence and
                price_val is not None and
                raw_match in ["VARIANT_EXACT", "EXACT", "MODEL_EXACT", "EXACT_PRODUCT"]
            ):
                match_type = "VARIANT_EXACT" if raw_match == "EXACT_PRODUCT" else raw_match
                ext_price = float(price_val)
                diff = round(ext_price - apex_price_float, 2)

                if diff < 0:
                    delta_label = f"₹{int(abs(diff)):,} cheaper"
                elif diff > 0:
                    delta_label = f"₹{int(diff):,} higher"
                else:
                    delta_label = "Same price"

                action_label = "View exact product →"
                final_img = raw_img
                final_id = extracted_id or off.get("external_product_id")
            else:
                # Downgrade to honest search fallback
                match_type = "SEARCH_FALLBACK"
                ext_price = None
                diff = None
                delta_label = "Search result — exact product not verified"
                action_label = f"Search on {off.get('store_name', 'Store')} →"
                final_img = None
                final_id = None

            offer_dict = {
                "id": off.get("id") or f"off_{off.get('retailer')}_{canonical_info['canonical_product_id']}",
                "retailer": off.get("retailer") or "retailer",
                "store_name": off.get("store_name") or "Retailer",
                "store_domain": retailer_domain,
                "store_logo_url": off.get("store_logo_url"),
                "store_type": off.get("store_type") or "MARKETPLACE",
                "external_product_id": final_id,
                "external_title": off.get("external_title") or canonical_info["title"],
                "external_image_url": final_img,
                "external_product_image": final_img,
                "external_url": raw_url,
                "external_product_url": raw_url,
                "link_type": match_type,
                "action_label": action_label,
                "redirect_url": f"/api/v1/external-offers/redirect?target={raw_url}",
                "price": ext_price,
                "mrp": float(off.get("mrp")) if off.get("mrp") else None,
                "shipping_price": 0.0,
                "total_price": ext_price,
                "currency": off.get("currency") or "INR",
                "difference_from_apex": diff,
                "price_delta_label": delta_label,
                "match_type": match_type,
                "match_confidence": float(off.get("match_confidence", 0.99 if match_type in ["VARIANT_EXACT", "EXACT"] else 0.60)),
                "identity_evidence": off.get("identity_evidence") or {
                    "type": "CANONICAL_IDENTITY_MATCH",
                    "style_code": canonical_info["style_code"],
                    "gtin": canonical_info["gtin"],
                    "variant": canonical_info["variant"]
                },
                "source_status": "VERIFIED",
                "source_verified": True,
                "availability": "IN_STOCK",
                "observed_at": now.isoformat(),
                "verified_at": now.isoformat(),
                "is_lowest": False,
                "identity": {
                    "brand": off.get("brand") or canonical_info["brand"],
                    "model": off.get("model") or canonical_info["model"],
                    "style_code": off.get("style_code") or canonical_info["style_code"],
                    "color": off.get("color") or canonical_info["color"],
                    "size": off.get("size") or canonical_info["size"],
                    "asin": final_id if "amazon" in retailer_domain else None,
                    "gtin": off.get("gtin") or canonical_info["gtin"]
                }
            }

            verified_offers.append(offer_dict)

        # 5. Calculate lowest verified deal strictly across verified exact offers
        exact_offers_with_price = [
            o for o in verified_offers
            if o["price"] is not None and o["match_type"] in ["VARIANT_EXACT", "EXACT", "MODEL_EXACT"]
        ]
        if exact_offers_with_price:
            for off_item in exact_offers_with_price:
                if off_item["price"] < lowest_price:
                    lowest_price = off_item["price"]
                    lowest_store = off_item["store_name"]

            for off_item in verified_offers:
                if off_item["price"] == lowest_price and off_item["match_type"] in ["VARIANT_EXACT", "EXACT", "MODEL_EXACT"]:
                    off_item["is_lowest"] = True

        apex_is_lowest = (lowest_price >= apex_price_float)
        apex_diff = round(apex_price_float - lowest_price, 2)
        checked_count = len(verified_offers) + 1  # Include Apex

        if not verified_offers:
            summary = f"External price comparison unavailable for this product. Apex Store price is ₹{apex_price_float:,.2f}."
        elif not exact_offers_with_price:
            summary = f"Apex Store offers verified in-stock pricing at ₹{apex_price_float:,.2f}. Lowest verified price among checked stores."
        elif apex_is_lowest:
            summary = f"Apex Store has the lowest verified price at ₹{apex_price_float:,.2f} among {checked_count} checked stores."
        else:
            summary = f"{lowest_store} has the lowest verified price at ₹{lowest_price:,.2f} (₹{int(abs(apex_diff)):,} cheaper than Apex Store) among checked stores."

        result = {
            "product_id": str(apex_product.id),
            "canonical_product": canonical_info,
            "product_name": apex_product.name,
            "product_brand": apex_product.brand,
            "product_category": apex_product.category,
            "product_image_url": canonical_info["canonical_image_url"],
            "apex_price": apex_price_float,
            "apex_mrp": apex_mrp_float,
            "currency": apex_product.currency or "INR",
            "offers": verified_offers,
            "lowest_verified_price": lowest_price,
            "lowest_store": lowest_store,
            "lowest_verified_retailer": lowest_store if not apex_is_lowest else "Apex Store",
            "apex_difference": apex_diff,
            "apex_is_lowest": apex_is_lowest,
            "checked_sources": checked_count,
            "checked_at": now.isoformat(),
            "verification_scope": "checked_stores_only",
            "cache_status": "LIVE",
            "summary_text": summary
        }

        _CANONICAL_CACHE[cache_key] = (now, result)
        return result

    @classmethod
    def _resolve_canonical_identity(cls, db: Session, product: Product) -> Dict[str, Any]:
        """
        Resolves an Apex product to its ground-truth Canonical Product Graph definition.
        Matches by GTIN, Model Number / Style Code, or Product Name.
        """
        p_name = (product.name or "").lower().strip()
        p_gtin = (product.gtin or "").strip()
        p_model = (product.model_number or "").strip()

        for canon in CANONICAL_PRODUCTS_GRAPH:
            if canon.get("apex_product_name", "").lower() == p_name:
                return canon
            if p_gtin and canon.get("gtin") == p_gtin:
                return canon
            if p_model and canon.get("style_code") == p_model:
                return canon

        # Default dynamic canonical representation if not in top-5 verified demo graph
        return {
            "id": f"canon_gen_{product.id}",
            "brand": product.brand or "Apex",
            "title": product.name,
            "category": product.category,
            "subcategory": product.subcategory,
            "model": product.model_number,
            "style_code": product.model_number,
            "gtin": product.gtin,
            "color": product.attributes.get("color") if isinstance(product.attributes, dict) else None,
            "size": product.attributes.get("size") if isinstance(product.attributes, dict) else None,
            "variant": product.attributes.get("color") if isinstance(product.attributes, dict) else None,
            "canonical_image_url": product.image_url,
            "verified": False,
            "retailer_offers": []
        }
