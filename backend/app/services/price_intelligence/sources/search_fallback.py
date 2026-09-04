import urllib.parse
from typing import Dict, Any, List, Optional

from .base import PriceIntelligenceSource, SourceCapability, SourceType

class SearchFallbackSource(PriceIntelligenceSource):
    """
    ₹0-Cost Honest Search Fallback Source.
    
    Generates transparent fallback query links for third-party marketplaces
    (Amazon India, Flipkart, Myntra, etc.) where active verified listings are unavailable.
    
    Strict Invariants:
    - price = None (never fabricates a numeric price)
    - image_url = None (never reuses Apex catalog image)
    - match_type = SEARCH_FALLBACK
    """

    FALLBACK_DOMAINS = {
        "amazon": {
            "name": "Amazon India",
            "domain": "amazon.in",
            "logo": "https://upload.wikimedia.org/wikipedia/commons/a/a9/Amazon_logo.svg",
            "search_template": "https://www.amazon.in/s?k={query}"
        },
        "flipkart": {
            "name": "Flipkart",
            "domain": "flipkart.com",
            "logo": "https://upload.wikimedia.org/wikipedia/en/thumb/7/7a/Flipkart_logo.svg/330px-Flipkart_logo.svg.png",
            "search_template": "https://www.flipkart.com/search?q={query}"
        },
        "myntra": {
            "name": "Myntra",
            "domain": "myntra.com",
            "logo": "https://constant.myntassets.com/web/assets/img/icon.5d108c858a0db793700f0be5d3ad1e120e01a500.png",
            "search_template": "https://www.myntra.com/{query_slug}"
        }
    }

    def __init__(self, retailer_key: str = "amazon"):
        self._retailer_key = retailer_key.lower()
        self._config = self.FALLBACK_DOMAINS.get(self._retailer_key, {
            "name": retailer_key.title(),
            "domain": f"{self._retailer_key}.com",
            "logo": None,
            "search_template": f"https://www.{self._retailer_key}.com/search?q={{query}}"
        })
        self._capabilities = SourceCapability(
            source_id=f"fallback_{self._retailer_key}",
            retailer_name=self._config["name"],
            source_type=SourceType.SEARCH_FALLBACK,
            enabled=True,
            supports_search=True,
            supports_product_lookup=False,
            supports_price=False,
            supports_images=False,
            supports_exact_pdp=False,
            requires_credentials=False
        )

    @property
    def capabilities(self) -> SourceCapability:
        return self._capabilities

    def discover_offers(self, canonical_product: Dict[str, Any]) -> List[Dict[str, Any]]:
        brand = canonical_product.get("brand") or ""
        style = canonical_product.get("style_code") or ""
        title = canonical_product.get("title") or canonical_product.get("apex_product_name") or "Product"

        query_str = f"{brand} {style or title}".strip()
        encoded_q = urllib.parse.quote_plus(query_str)
        slug_q = query_str.lower().replace(" ", "-")

        template = self._config["search_template"]
        if "{query_slug}" in template:
            search_url = template.format(query_slug=slug_q)
        else:
            search_url = template.format(query=encoded_q)

        return [{
            "source_id": self.source_id,
            "source_type": SourceType.SEARCH_FALLBACK.value,
            "retailer": self._retailer_key,
            "store_name": self._config["name"],
            "store_domain": self._config["domain"],
            "store_logo_url": self._config["logo"],
            "external_product_id": None,
            "external_title": f"Search '{query_str}' on {self._config['name']}",
            "external_product_image": None,
            "external_image_url": None,
            "external_url": search_url,
            "external_product_url": search_url,
            "price": None,
            "mrp": None,
            "currency": "INR",
            "match_type": "SEARCH_FALLBACK",
            "match_confidence": 0.60,
            "action_label": f"Search on {self._config['name']} →",
            "identity_evidence": {
                "type": "SEARCH_FALLBACK",
                "reason": f"Direct active {self._config['name']} listing unverified"
            },
            "source": f"{self._config['name']} Search Fallback",
            "observed_at": None
        }]
