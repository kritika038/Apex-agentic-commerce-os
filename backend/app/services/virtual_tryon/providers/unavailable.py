from typing import Dict, Any, Optional, Tuple
from app.services.virtual_tryon.base import VirtualTryOnProvider

class UnavailableVirtualTryOnProvider(VirtualTryOnProvider):
    """
    Fallback Provider representing a disabled or unconfigured VTO environment.
    """

    def __init__(self, reason: str = "Virtual Try-On provider is not configured."):
        self._reason = reason

    @property
    def provider_id(self) -> str:
        return "unavailable"

    @property
    def is_available(self) -> bool:
        return False

    @property
    def is_demo(self) -> bool:
        return False

    def generate_try_on(
        self,
        person_image_bytes: bytes,
        product_image_url: str,
        garment_type: str,
        product_metadata: Dict[str, Any],
        progress_callback: Optional[Any] = None
    ) -> Tuple[bool, Optional[bytes], Optional[str], Optional[str]]:
        return False, None, "PROVIDER_UNAVAILABLE", self._reason
