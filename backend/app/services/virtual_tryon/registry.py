import os
from typing import Dict, Optional
from app.services.virtual_tryon.base import VirtualTryOnProvider
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
        provider_name = (name or os.environ.get("VIRTUAL_TRYON_PROVIDER", "local_fashn")).lower().strip()
        is_enabled = os.environ.get("VIRTUAL_TRYON_ENABLED", "true").lower() in ["true", "1", "yes"]

        if not is_enabled:
            return UnavailableVirtualTryOnProvider("Virtual Try-On is currently disabled by administrator.")

        if provider_name in ["local_fashn", "local", "local_vton", "local-vton", "fashn-vton-1.5"]:
            key = "local_fashn"
            if key not in cls._providers:
                cls._providers[key] = LocalFashnVTONProvider()
            return cls._providers[key]

        if provider_name in ["fashn", "hosted_fashn", "hosted", "production", "live", "tryon-v1.6"]:
            key = "fashn"
            if key not in cls._providers:
                cls._providers[key] = FashnVirtualTryOnProvider()
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

