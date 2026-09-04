from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from decimal import Decimal
from pydantic import BaseModel

class ExternalOfferData(BaseModel):
    store_name: str
    store_domain: str
    store_type: str # RETAILER, OFFICIAL_BRAND, MARKETPLACE
    logo_url: Optional[str] = None
    external_product_id: Optional[str] = None
    external_product_title: str
    external_url: str
    affiliate_url: Optional[str] = None
    image_url: Optional[str] = None
    price: Decimal
    mrp: Optional[Decimal] = None
    currency: str = "INR"
    availability: str = "IN_STOCK" # IN_STOCK, OUT_OF_STOCK, UNKNOWN
    match_type: str = "EXACT" # EXACT, VARIANT_EXACT, HIGH_CONFIDENCE, SIMILAR
    match_confidence: float = 1.0
    match_reason: Optional[str] = None
    source_status: str = "VERIFIED" # LIVE, VERIFIED, CACHED, SEEDED_DEMO, UNAVAILABLE
    source_verified: bool = True

class ExternalStoreConnector(ABC):
    """
    Abstract Base Class for External Store & Retailer Connectors.
    Allows plug-and-play addition of new official retailer and brand sources.
    """

    def __init__(self, store_name: str, domain: str, store_type: str = "RETAILER", is_live: bool = False):
        self.store_name = store_name
        self.domain = domain
        self.store_type = store_type
        self.is_live = is_live

    @abstractmethod
    def search_products(self, query: str, brand: Optional[str] = None, category: Optional[str] = None) -> List[ExternalOfferData]:
        """Searches external catalog for matching candidates."""
        pass

    @abstractmethod
    def get_offer_for_product(self, product_dict: Dict[str, Any]) -> Optional[ExternalOfferData]:
        """Resolves specific product to verified external offer."""
        pass

    @abstractmethod
    def build_product_url(self, external_product_id: str, clean_title: Optional[str] = None) -> str:
        """Constructs secure, canonical outbound destination URL."""
        pass
