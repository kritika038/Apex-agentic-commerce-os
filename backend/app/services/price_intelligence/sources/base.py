from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel

class SourceType(str, Enum):
    OFFICIAL_D2C = "OFFICIAL_D2C"
    PUBLIC_STRUCTURED = "PUBLIC_STRUCTURED"
    MERCHANT_FEED = "MERCHANT_FEED"
    AUTHORIZED_API = "AUTHORIZED_API"
    SEARCH_FALLBACK = "SEARCH_FALLBACK"

class SourceCapability(BaseModel):
    source_id: str
    retailer_name: str
    source_type: SourceType
    enabled: bool = True
    supports_search: bool = True
    supports_product_lookup: bool = True
    supports_price: bool = True
    supports_images: bool = True
    supports_exact_pdp: bool = True
    requires_credentials: bool = False

class PriceIntelligenceSource(ABC):
    """
    Abstract Base Class for pluggable price intelligence sources.
    Operates at ₹0-cost with zero dependence on paid or scraping services.
    """

    @property
    @abstractmethod
    def capabilities(self) -> SourceCapability:
        """Declares the source type and functional capabilities."""
        pass

    @property
    def source_id(self) -> str:
        return self.capabilities.source_id

    @property
    def retailer_name(self) -> str:
        return self.capabilities.retailer_name

    @property
    def source_type(self) -> SourceType:
        return self.capabilities.source_type

    @property
    def is_enabled(self) -> bool:
        return self.capabilities.enabled

    @abstractmethod
    def discover_offers(self, canonical_product: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Discovers candidate listings/offers for a canonical product identity.
        Returns normalized raw offer payloads.
        """
        pass
