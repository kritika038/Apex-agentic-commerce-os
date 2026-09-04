import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .base import PriceIntelligenceSource, SourceType
from .d2c import OfficialD2CSource
from .structured_data import PublicStructuredDataSource
from .merchant_feed import MerchantFeedSource
from .search_fallback import SearchFallbackSource
from app.services.price_intelligence.validators import (
    validate_retailer_pdp_url,
    validate_external_product_image
)

logger = logging.getLogger(__name__)

class PriceIntelligenceSourceRegistry:
    """
    Central Registry and Orchestrator for pluggable ₹0-cost Price Intelligence Sources.
    
    Orchestration Flow:
    Canonical Product Identity
            ↓
    Source Registry (D2C, Public Structured, Merchant Feed, Fallbacks, Authorized APIs)
            ↓
    Candidate Offers Discovery
            ↓
    Strict Identity & Provenance Verification
            ↓
    Normalized Multi-Store Comparison
    """

    def __init__(self):
        self._sources: Dict[str, PriceIntelligenceSource] = {}
        self._init_default_sources()

    def _init_default_sources(self):
        """Initializes default ₹0-cost sources."""
        # 1. Official D2C Sources
        self.register_source(OfficialD2CSource("Nike", "Nike Official Store", "nike.com"))
        self.register_source(OfficialD2CSource("Adidas", "Adidas Official Store", "adidas.co.in"))
        self.register_source(OfficialD2CSource("Puma", "Puma Official Direct", "puma.com"))

        # 2. Public Structured Data Source (Schema.org / JSON-LD)
        self.register_source(PublicStructuredDataSource())

        # 3. Merchant Feed Source
        self.register_source(MerchantFeedSource())

        # 4. Search Fallback Sources (Amazon India, Flipkart, Myntra)
        self.register_source(SearchFallbackSource("amazon"))
        self.register_source(SearchFallbackSource("flipkart"))
        self.register_source(SearchFallbackSource("myntra"))

    def register_source(self, source: PriceIntelligenceSource):
        self._sources[source.source_id] = source

    def get_source(self, source_id: str) -> Optional[PriceIntelligenceSource]:
        return self._sources.get(source_id)

    def list_sources(self) -> List[PriceIntelligenceSource]:
        return list(self._sources.values())

    def discover_and_verify_offers(
        self,
        canonical_product: Dict[str, Any],
        apex_price: float,
        apex_image_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Discovers and verifies offers across all registered sources for a canonical product.
        Applies strict identity verification, price verification, image provenance, and PDP checks.
        """
        candidates: List[Dict[str, Any]] = []

        # 1. Gather candidate offers from enabled sources
        for source in self._sources.values():
            if not source.is_enabled:
                continue
            try:
                offers = source.discover_offers(canonical_product)
                candidates.extend(offers)
            except Exception as e:
                logger.error(f"Error discovering offers from source '{source.source_id}': {e}")

        # 2. Deduplicate candidate offers by domain
        deduped_map: Dict[str, Dict[str, Any]] = {}
        for cand in candidates:
            domain = cand.get("store_domain") or cand.get("retailer") or "unknown"
            existing = deduped_map.get(domain)
            if not existing:
                deduped_map[domain] = cand
            else:
                # Prefer verified exact offer over fallback
                if cand.get("match_type") in ["VARIANT_EXACT", "EXACT", "MODEL_EXACT"] and existing.get("match_type") == "SEARCH_FALLBACK":
                    deduped_map[domain] = cand

        # 3. Verify each offer strictly
        verified_results: List[Dict[str, Any]] = []
        now_str = datetime.now(timezone.utc).isoformat()

        for cand in deduped_map.values():
            domain = cand.get("store_domain") or ""
            raw_url = cand.get("external_product_url") or cand.get("external_url") or ""
            raw_img = cand.get("external_product_image") or cand.get("external_image_url")
            raw_match = cand.get("match_type", "SEARCH_FALLBACK")
            price_val = cand.get("price")
            evidence = cand.get("identity_evidence") or {}

            # Strict validations
            is_valid_pdp, extracted_id = validate_retailer_pdp_url(domain, raw_url)
            is_valid_img, _ = validate_external_product_image(raw_img, apex_image_url)
            has_identity_evidence = bool(
                evidence and evidence.get("type") not in ["SEARCH_FALLBACK", "UNVERIFIED"]
            )
            canonical_is_verified = bool(canonical_product.get("verified", True))

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
                diff = round(ext_price - apex_price, 2)
                delta_label = f"₹{int(abs(diff)):,} cheaper" if diff < 0 else (f"₹{int(diff):,} higher" if diff > 0 else "Same price")
                action_label = "View exact product →"
                final_img = raw_img
                final_id = extracted_id or cand.get("external_product_id")
            else:
                # Downgrade to honest search fallback
                match_type = "SEARCH_FALLBACK"
                ext_price = None
                diff = None
                delta_label = "Search result — exact product not verified"
                action_label = f"Search on {cand.get('store_name', 'Store')} →"
                final_img = None
                final_id = None

            verified_results.append({
                "id": cand.get("id") or f"off_{cand.get('retailer')}_{canonical_product.get('canonical_product_id')}",
                "retailer": cand.get("retailer") or "store",
                "store_name": cand.get("store_name") or "Retailer",
                "store_domain": domain,
                "store_logo_url": cand.get("store_logo_url"),
                "store_type": cand.get("source_type") or "MARKETPLACE",
                "external_product_id": final_id,
                "external_title": cand.get("external_title") or canonical_product.get("title"),
                "external_product_image": final_img,
                "external_image_url": final_img,
                "external_url": raw_url,
                "external_product_url": raw_url,
                "link_type": match_type,
                "action_label": action_label,
                "redirect_url": f"/api/v1/external-offers/redirect?target={raw_url}",
                "price": ext_price,
                "mrp": float(cand.get("mrp")) if cand.get("mrp") else None,
                "shipping_price": 0.0,
                "total_price": ext_price,
                "currency": cand.get("currency", "INR"),
                "difference_from_apex": diff,
                "price_delta_label": delta_label,
                "match_type": match_type,
                "match_confidence": float(cand.get("match_confidence", 0.99 if match_type == "VARIANT_EXACT" else 0.60)),
                "identity_evidence": evidence or {
                    "type": "CANONICAL_IDENTITY_MATCH",
                    "style_code": canonical_product.get("style_code"),
                    "gtin": canonical_product.get("gtin"),
                    "variant": canonical_product.get("variant")
                },
                "source_status": "VERIFIED",
                "source_verified": True,
                "availability": "IN_STOCK",
                "observed_at": now_str,
                "verified_at": now_str,
                "is_lowest": False,
                "identity": {
                    "brand": cand.get("brand") or canonical_product.get("brand"),
                    "model": cand.get("model") or canonical_product.get("model"),
                    "style_code": cand.get("style_code") or canonical_product.get("style_code"),
                    "color": cand.get("color") or canonical_product.get("color"),
                    "size": cand.get("size") or canonical_product.get("size"),
                    "gtin": cand.get("gtin") or canonical_product.get("gtin")
                }
            })

        return verified_results
