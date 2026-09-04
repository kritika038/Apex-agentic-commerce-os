import os
from typing import Dict, Optional
from app.core.config import settings
from app.services.virtual_tryon.base import VirtualTryOnProvider
from app.services.virtual_tryon.providers.huggingface_zerogpu import HuggingFaceZeroGPUProvider
from app.services.virtual_tryon.providers.local_fashn import LocalFashnVTONProvider
from app.services.virtual_tryon.providers.fashn import FashnVirtualTryOnProvider
from app.services.virtual_tryon.providers.demo import DemoVirtualTryOnProvider
from app.services.virtual_tryon.providers.generic_api import GenericApiVirtualTryOnProvider
from app.services.virtual_tryon.providers.unavailable import UnavailableVirtualTryOnProvider

class VTOProviderRegistry:
    """
    Registry for Virtual Try-On Providers.
    Dynamically routes requests according to backend environment configuration.
    """

    _providers: Dict[str, VirtualTryOnProvider] = {}

    @classmethod
    def get_provider(cls, name: Optional[str] = None) -> VirtualTryOnProvider:
        raw_enabled = os.environ.get("VIRTUAL_TRYON_ENABLED")
        if raw_enabled is not None:
            is_enabled = raw_enabled.lower() in ["true", "1", "yes"]
        else:
            is_enabled = getattr(settings, "VIRTUAL_TRYON_ENABLED", True)

        if not is_enabled:
            return UnavailableVirtualTryOnProvider("Virtual Try-On is currently disabled by administrator.")

        provider_name = (
            name 
            or os.environ.get("VIRTUAL_TRYON_PROVIDER") 
            or getattr(settings, "VIRTUAL_TRYON_PROVIDER", "huggingface_zerogpu")
        ).strip().strip("'\"").strip().lower()

        if provider_name in [
            "huggingface_zerogpu",
            "huggingface-zerogpu",
            "hugging_face_zerogpu",
            "hf_zerogpu",
            "hf-zerogpu",
            "huggingface",
            "hf",
            "zerogpu",
            "hf_space",
            "kritika68-apex-vton",
        ]:
            key = "huggingface_zerogpu"
            if key not in cls._providers:
                cls._providers[key] = HuggingFaceZeroGPUProvider()
            return cls._providers[key]

        if provider_name in ["fashn", "hosted_fashn", "hosted", "production", "live", "tryon-v1.6"]:
            key = "fashn"
            if key not in cls._providers:
                cls._providers[key] = FashnVirtualTryOnProvider()
            return cls._providers[key]

        if provider_name in ["local_fashn", "local", "local_vton", "local-vton", "fashn-vton-1.5"]:
            key = "local_fashn"
            if key not in cls._providers:
                cls._providers[key] = LocalFashnVTONProvider()
            return cls._providers[key]

        if provider_name in ["api", "generic_api"]:
            key = "generic_api"
            if key not in cls._providers:
                cls._providers[key] = GenericApiVirtualTryOnProvider()
            return cls._providers[key]

        if provider_name in ["demo", "test", "mock", "simulated"]:
            key = "demo"
            if key not in cls._providers:
                cls._providers[key] = DemoVirtualTryOnProvider()
            return cls._providers[key]

        return UnavailableVirtualTryOnProvider(f"Unknown VTO provider '{provider_name}'.")

    @classmethod
    def clear_cache(cls):
        cls._providers.clear()


