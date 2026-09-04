from .base import ExternalStoreConnector, ExternalOfferData
from .registry import ExternalStoreRegistry, ALLOWED_EXTERNAL_DOMAINS
from .amazon import AmazonStoreConnector
from .flipkart import FlipkartStoreConnector
from .myntra import MyntraStoreConnector
from .brand_store import BrandOfficialStoreConnector

# Register default stores
ExternalStoreRegistry.register(AmazonStoreConnector())
ExternalStoreRegistry.register(FlipkartStoreConnector())
ExternalStoreRegistry.register(MyntraStoreConnector())
ExternalStoreRegistry.register(BrandOfficialStoreConnector("Nike", "nike.com", "https://www.nike.com/in/w/running-shoes-37v7j"))
ExternalStoreRegistry.register(BrandOfficialStoreConnector("Adidas", "adidas.co.in", "https://www.adidas.co.in/running-shoes"))
ExternalStoreRegistry.register(BrandOfficialStoreConnector("Puma", "puma.com", "https://in.puma.com/in/en/mens/mens-shoes/mens-running-shoes"))
ExternalStoreRegistry.register(BrandOfficialStoreConnector("Decathlon", "decathlon.in", "https://www.decathlon.in/c/running-shoes-17387"))

__all__ = [
    "ExternalStoreConnector",
    "ExternalOfferData",
    "ExternalStoreRegistry",
    "ALLOWED_EXTERNAL_DOMAINS",
    "AmazonStoreConnector",
    "FlipkartStoreConnector",
    "MyntraStoreConnector",
    "BrandOfficialStoreConnector"
]
