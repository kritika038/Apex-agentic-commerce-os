import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from urllib.parse import urlparse

from .base import PriceIntelligenceSource, SourceCapability, SourceType

logger = logging.getLogger(__name__)

class PublicStructuredDataSource(PriceIntelligenceSource):
    """
    ₹0-Cost Schema.org / JSON-LD Structured Product Data Source.
    
    Parses publicly accessible Schema.org Product & Offer structured metadata
    without aggressive scraping or anti-bot bypass.
    
    Strict Field Invariants:
    - If price is not present -> price = None
    - If GTIN is not present -> gtin = None
    - If image is not present -> image_url = None
    - Provenance strictly tagged as PUBLIC_STRUCTURED.
    """

    def __init__(self, source_id: str = "public_structured_data", retailer_name: str = "Public Structured Source"):
        self._source_id = source_id
        self._retailer_name = retailer_name
        self._capabilities = SourceCapability(
            source_id=source_id,
            retailer_name=retailer_name,
            source_type=SourceType.PUBLIC_STRUCTURED,
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

    @classmethod
    def parse_json_ld_payload(cls, json_ld_data: Any, target_url: str) -> Optional[Dict[str, Any]]:
        """
        Parses Schema.org JSON-LD object (single dict, list of dicts, or @graph)
        into normalized product & offer metadata.
        """
        if isinstance(json_ld_data, list):
            for item in json_ld_data:
                res = cls.parse_json_ld_payload(item, target_url)
                if res:
                    return res
            return None

        if not isinstance(json_ld_data, dict):
            return None

        # Check @graph array
        if "@graph" in json_ld_data and isinstance(json_ld_data["@graph"], list):
            return cls.parse_json_ld_payload(json_ld_data["@graph"], target_url)

        type_field = json_ld_data.get("@type", "")
        types = [type_field] if isinstance(type_field, str) else type_field
        if not any("Product" in str(t) for t in types):
            return None

        # Extract Product Identity Fields
        title = json_ld_data.get("name")
        brand_raw = json_ld_data.get("brand")
        brand = brand_raw.get("name") if isinstance(brand_raw, dict) else (brand_raw if isinstance(brand_raw, str) else None)
        
        sku = json_ld_data.get("sku")
        mpn = json_ld_data.get("mpn")
        gtin = (
            json_ld_data.get("gtin13") or
            json_ld_data.get("gtin14") or
            json_ld_data.get("gtin12") or
            json_ld_data.get("gtin8") or
            json_ld_data.get("gtin")
        )

        # Extract Product Image
        img_raw = json_ld_data.get("image")
        image_url = None
        if isinstance(img_raw, str):
            image_url = img_raw
        elif isinstance(img_raw, list) and img_raw:
            image_url = img_raw[0] if isinstance(img_raw[0], str) else img_raw[0].get("url")
        elif isinstance(img_raw, dict):
            image_url = img_raw.get("url") or img_raw.get("contentUrl")

        # Extract Offer / Pricing Information
        offers_raw = json_ld_data.get("offers")
        price = None
        currency = "INR"
        availability = "IN_STOCK"
        pdp_url = json_ld_data.get("url") or target_url

        if isinstance(offers_raw, list) and offers_raw:
            offer = offers_raw[0]
        elif isinstance(offers_raw, dict):
            offer = offers_raw
        else:
            offer = None

        if offer:
            price_val = offer.get("price") or offer.get("lowPrice")
            if price_val is not None:
                try:
                    price = float(str(price_val).replace(",", "").strip())
                except (ValueError, TypeError):
                    price = None
            currency = offer.get("priceCurrency") or "INR"
            avail_str = str(offer.get("availability") or "").lower()
            availability = "IN_STOCK" if "instock" in avail_str or "in_stock" in avail_str else "OUT_OF_STOCK"
            if offer.get("url"):
                pdp_url = offer.get("url")

        domain = urlparse(target_url).hostname or "external-source"
        if domain.startswith("www."):
            domain = domain[4:]

        return {
            "source_type": SourceType.PUBLIC_STRUCTURED.value,
            "retailer": domain.split(".")[0],
            "store_name": domain.title(),
            "store_domain": domain,
            "external_product_id": sku or mpn or gtin,
            "external_title": title,
            "external_product_image": image_url,
            "external_image_url": image_url,
            "external_url": pdp_url,
            "external_product_url": pdp_url,
            "price": price,
            "currency": currency,
            "brand": brand,
            "style_code": mpn or sku,
            "gtin": gtin,
            "availability": availability,
            "source": "PUBLIC_STRUCTURED_JSON_LD",
            "observed_at": datetime.now(timezone.utc).isoformat()
        }

    def discover_offers(self, canonical_product: Dict[str, Any]) -> List[Dict[str, Any]]:
        # In ₹0 mode, structured data can be provided via canonical attributes or merchant feeds
        structured_entries = canonical_product.get("structured_data_offers") or []
        parsed_offers = []
        for entry in structured_entries:
            parsed = self.parse_json_ld_payload(entry.get("payload"), entry.get("url", ""))
            if parsed:
                parsed_offers.append(parsed)
        return parsed_offers
