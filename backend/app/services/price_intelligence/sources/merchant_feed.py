from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from decimal import Decimal

from .base import PriceIntelligenceSource, SourceCapability, SourceType

class MerchantFeedSource(PriceIntelligenceSource):
    """
    ₹0-Cost Merchant Feed Source.
    
    Allows merchants to supply direct product mappings, verified pricing feeds,
    and verified competitor benchmark observations.
    
    Strict Invariant:
    All entries are explicitly labeled as MERCHANT_PROVIDED to preserve transparency.
    """

    def __init__(self, merchant_id: Optional[str] = None):
        self._merchant_id = merchant_id or "default_merchant"
        self._capabilities = SourceCapability(
            source_id=f"merchant_feed_{self._merchant_id}",
            retailer_name="Merchant Verified Feed",
            source_type=SourceType.MERCHANT_FEED,
            enabled=True,
            supports_search=False,
            supports_product_lookup=True,
            supports_price=True,
            supports_images=True,
            supports_exact_pdp=True,
            requires_credentials=False
        )

    @property
    def capabilities(self) -> SourceCapability:
        return self._capabilities

    def discover_offers(self, canonical_product: Dict[str, Any]) -> List[Dict[str, Any]]:
        feed_entries = canonical_product.get("merchant_feed_offers") or []
        offers = []

        for entry in feed_entries:
            price = entry.get("price")
            offers.append({
                "source_id": self.source_id,
                "source_type": SourceType.MERCHANT_FEED.value,
                "retailer": entry.get("retailer") or "merchant_partner",
                "store_name": entry.get("store_name") or "Merchant Partner",
                "store_domain": entry.get("store_domain") or "merchant-feed.local",
                "store_logo_url": entry.get("store_logo_url"),
                "external_product_id": entry.get("sku") or entry.get("gtin") or entry.get("external_product_id"),
                "external_title": entry.get("title") or canonical_product.get("title"),
                "external_product_image": entry.get("image_url"),
                "external_image_url": entry.get("image_url"),
                "external_url": entry.get("pdp_url") or entry.get("external_url"),
                "external_product_url": entry.get("pdp_url") or entry.get("external_url"),
                "price": float(price) if price is not None else None,
                "mrp": float(entry.get("mrp")) if entry.get("mrp") is not None else None,
                "currency": entry.get("currency", "INR"),
                "brand": entry.get("brand") or canonical_product.get("brand"),
                "style_code": entry.get("style_code") or canonical_product.get("style_code"),
                "gtin": entry.get("gtin") or canonical_product.get("gtin"),
                "match_type": entry.get("match_type", "VARIANT_EXACT"),
                "match_confidence": float(entry.get("match_confidence", 0.95)),
                "identity_evidence": {
                    "type": "MERCHANT_PROVIDED_FEED",
                    "merchant_id": self._merchant_id,
                    "style_code": entry.get("style_code") or canonical_product.get("style_code"),
                    "gtin": entry.get("gtin") or canonical_product.get("gtin"),
                    "verified_at": datetime.now(timezone.utc).isoformat()
                },
                "source": "MERCHANT_PROVIDED_FEED",
                "observed_at": entry.get("observed_at") or datetime.now(timezone.utc).isoformat()
            })

        return offers
