from typing import Dict, List, Optional, Set
from urllib.parse import urlparse
from .base import ExternalStoreConnector

# Security Whitelist: Explicitly allowed domains for outbound redirection
# Prevents open-redirect vulnerabilities. Only legitimate verified domains are permitted.
ALLOWED_EXTERNAL_DOMAINS: Set[str] = {
    "amazon.in",
    "www.amazon.in",
    "amazon.com",
    "www.amazon.com",
    "amzn.in",
    "flipkart.com",
    "www.flipkart.com",
    "fkrt.it",
    "myntra.com",
    "www.myntra.com",
    "nike.com",
    "www.nike.com",
    "adidas.co.in",
    "www.adidas.co.in",
    "puma.com",
    "in.puma.com",
    "decathlon.in",
    "www.decathlon.in",
    "asics.com",
    "www.asics.com",
    "levi.in",
    "www.levi.in",
    "philips.co.in",
    "www.philips.co.in",
    "nivea.in",
    "www.nivea.in",
    "croma.com",
    "www.croma.com",
    "reliancedigital.in",
    "www.reliancedigital.in",
    "ajio.com",
    "www.ajio.com",
    "apple.com",
    "www.apple.com",
    "boat-lifestyle.com",
    "www.boat-lifestyle.com",
    "gonoise.com",
    "www.gonoise.com",
    "sony.co.in",
    "www.sony.co.in",
    "americantourister.in",
    "www.americantourister.in",
    "milton.in",
    "www.milton.in",
    "prestigexclusive.in",
    "www.prestigexclusive.in",
    "fossil.com",
    "www.fossil.com",
    "ray-ban.com",
    "www.ray-ban.com"
}

class ExternalStoreRegistry:
    """
    Central Registry for external store connectors and domain security checks.
    """
    _connectors: Dict[str, ExternalStoreConnector] = {}

    @classmethod
    def register(cls, connector: ExternalStoreConnector):
        cls._connectors[connector.domain] = connector

    @classmethod
    def get_connector(cls, domain: str) -> Optional[ExternalStoreConnector]:
        return cls._connectors.get(domain)

    @classmethod
    def list_connectors(cls) -> List[ExternalStoreConnector]:
        return list(cls._connectors.values())

    @staticmethod
    def is_domain_allowed(url: str) -> bool:
        """
        Validates whether target URL belongs to an explicitly authorized external retailer.
        Rejects non-HTTP(S), javascript:, data:, and unverified domain targets.
        """
        if not url:
            return False
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            hostname = (parsed.hostname or "").lower()
            if hostname in ALLOWED_EXTERNAL_DOMAINS:
                return True
            # Match parent domain if registered (e.g. store.nike.com matches nike.com)
            for allowed in ALLOWED_EXTERNAL_DOMAINS:
                if hostname.endswith("." + allowed) or hostname == allowed:
                    return True
            return False
        except Exception:
            return False
