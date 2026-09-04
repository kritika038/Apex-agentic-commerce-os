from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple

class VirtualTryOnProvider(ABC):
    """
    Abstract Base Class for Virtual Try-On AI Providers.
    Decouples Apex Commerce OS from any specific vendor (Google Vertex, HuggingFace, Replicate, custom diffusion, etc.).
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier (e.g. 'demo', 'vertex_vto', 'replicate_idm_vton')."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether the provider is currently configured and operational."""
        pass

    @property
    @abstractmethod
    def is_demo(self) -> bool:
        """Whether this provider produces labeled demo simulations rather than live model inferences."""
        pass

    @abstractmethod
    def generate_try_on(
        self,
        person_image_bytes: bytes,
        product_image_url: str,
        garment_type: str,
        product_metadata: Dict[str, Any],
        progress_callback: Optional[Any] = None
    ) -> Tuple[bool, Optional[bytes], Optional[str], Optional[str]]:
        """
        Executes virtual try-on visual synthesis with optional real-time progress callbacks.
        
        progress_callback signature:
            callback(stage: str, percent: int, step: Optional[int], total: Optional[int], message: str)

        Returns:
            (success: bool, result_image_bytes: Optional[bytes], error_code: Optional[str], error_message: Optional[str])
        """
        pass
