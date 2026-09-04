from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple

class BaseRetailerAdapter(ABC):
    """
    Standard interface for external marketplace and retailer price intelligence adapters.
    """

    @property
    @abstractmethod
    def retailer_name(self) -> str:
        pass

    @property
    @abstractmethod
    def domain(self) -> str:
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Returns True if the retailer adapter is configured and active."""
        pass

    @abstractmethod
    def search_products(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Searches the retailer API for candidate product listings."""
        pass

    @abstractmethod
    def get_product(self, external_product_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves exact listing details by retailer product identifier (e.g. ASIN)."""
        pass

    @abstractmethod
    def normalize_listing(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes raw retailer API payload into standard listing format."""
        pass

    @abstractmethod
    def normalize_offer(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extracts and normalizes live offer/price from raw retailer API payload."""
        pass

    @abstractmethod
    def verify_identity(
        self,
        canonical_product: Dict[str, Any],
        raw_or_normalized_item: Dict[str, Any]
    ) -> Tuple[bool, str, float, Dict[str, Any]]:
        """
        Verifies whether a candidate retailer listing corresponds to the canonical product.
        Returns: (is_match, match_type, match_confidence, identity_evidence)
        """
        pass
