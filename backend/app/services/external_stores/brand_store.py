from typing import Dict, Any, List, Optional
from decimal import Decimal
import urllib.parse
from .base import ExternalStoreConnector, ExternalOfferData

class BrandOfficialStoreConnector(ExternalStoreConnector):
    def __init__(self, brand_name: str, domain: str, official_url: str):
        super().__init__(
            store_name=f"{brand_name} Official",
            domain=domain,
            store_type="OFFICIAL_BRAND",
            is_live=False
        )
        self.brand_name = brand_name
        self.official_url = official_url

    def search_products(self, query: str, brand: Optional[str] = None, category: Optional[str] = None) -> List[ExternalOfferData]:
        return []

    def get_offer_for_product(self, product_dict: Dict[str, Any]) -> Optional[ExternalOfferData]:
        title = product_dict.get("name", "Product")
        price = Decimal(str(product_dict.get("mrp") or product_dict.get("price", "0.00")))
        
        return ExternalOfferData(
            store_name=self.store_name,
            store_domain=self.domain,
            store_type=self.store_type,
            external_product_id=product_dict.get("model_number") or product_dict.get("sku"),
            external_product_title=f"{title} - Official Store",
            external_url=self.official_url,
            price=price,
            currency="INR",
            availability="IN_STOCK",
            match_type="EXACT",
            match_confidence=1.0,
            match_reason="Manufacturer Direct / Official Listing",
            source_status="VERIFIED",
            source_verified=True
        )

    def build_product_url(self, external_product_id: str, clean_title: Optional[str] = None) -> str:
        return self.official_url
