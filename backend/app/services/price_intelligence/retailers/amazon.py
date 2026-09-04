import logging
import urllib.parse
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import httpx

from app.core.config import settings
from .base import BaseRetailerAdapter

logger = logging.getLogger(__name__)

class AmazonCreatorsAdapter(BaseRetailerAdapter):
    """
    Amazon Creators API Marketplace Connector.
    
    Implements:
    - OAuth 2.0 Client Credentials Authentication
    - SearchItems & GetItems with OffersV2, Images, ItemInfo
    - Deterministic Physical Identity Verification (GTIN, Manufacturer Style Code)
    - Real Image Provenance (Amazon CDN)
    - Affiliate / Partner Tag Link Generation
    - Safe Graceful Degradation to SEARCH_FALLBACK on missing credentials, rate limiting, or API errors.
    """

    def __init__(
        self,
        enabled: Optional[bool] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        partner_tag: Optional[str] = None,
        marketplace: Optional[str] = None,
        api_host: Optional[str] = None,
        http_client: Optional[httpx.Client] = None
    ):
        self._enabled = enabled if enabled is not None else getattr(settings, "AMAZON_CREATORS_API_ENABLED", False)
        self._client_id = client_id or getattr(settings, "AMAZON_CLIENT_ID", "")
        self._client_secret = client_secret or getattr(settings, "AMAZON_CLIENT_SECRET", "")
        self._partner_tag = partner_tag or getattr(settings, "AMAZON_PARTNER_TAG", "")
        self._marketplace = marketplace or getattr(settings, "AMAZON_MARKETPLACE", "www.amazon.in")
        self._api_host = api_host or getattr(settings, "AMAZON_CREATORS_API_HOST", "webservices.amazon.in")
        
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._http_client = http_client

    @property
    def retailer_name(self) -> str:
        return "Amazon India"

    @property
    def domain(self) -> str:
        return "amazon.in"

    def is_enabled(self) -> bool:
        """Connector is active only when feature flag is True and client credentials exist."""
        return bool(self._enabled and self._client_id and self._client_secret)

    def _get_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=10.0)

    def _get_access_token(self) -> Optional[str]:
        """Obtains OAuth 2.0 token via Client Credentials grant."""
        if not self.is_enabled():
            return None

        now = datetime.now(timezone.utc)
        if self._token and self._token_expires_at and now < self._token_expires_at:
            return self._token

        token_url = f"https://api.amazon.com/auth/o2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "creators::api"
        }

        try:
            client = self._get_client()
            resp = client.post(token_url, data=payload)
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = now + timedelta(seconds=max(60, expires_in - 120))
                return self._token
            else:
                logger.warning(f"Amazon Creators OAuth failed with status {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"Amazon Creators OAuth token request error: {str(e)}")
            return None

    def search_products(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Executes SearchItems request against Amazon Creators API.
        Returns list of raw candidate items.
        """
        if not self.is_enabled():
            return []

        token = self._get_access_token()
        if not token:
            return []

        endpoint = f"https://{self._api_host}/paapi5/searchitems"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "x-amz-target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
        }

        payload = {
            "Keywords": query,
            "Marketplace": self._marketplace,
            "PartnerTag": self._partner_tag,
            "PartnerType": "Associates",
            "ItemCount": 5,
            "Resources": [
                "ItemInfo.Title",
                "ItemInfo.ByLineInfo",
                "ItemInfo.ProductInfo",
                "ItemInfo.Classifications",
                "ItemInfo.ExternalIds",
                "Images.Primary.Large",
                "OffersV2.Listings.Price",
                "OffersV2.Listings.Availability",
                "Offers.Listings.Price",
                "ParentASIN"
            ]
        }

        if filters and filters.get("search_index"):
            payload["SearchIndex"] = filters["search_index"]

        try:
            client = self._get_client()
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("SearchResult", {}).get("Items", [])
                return items
            elif resp.status_code == 429:
                logger.warning("Amazon Creators API rate limited (429).")
                return []
            else:
                logger.warning(f"Amazon SearchItems returned {resp.status_code}")
                return []
        except Exception as e:
            logger.error(f"Amazon SearchItems execution failed: {str(e)}")
            return []

    def get_product(self, external_product_id: str) -> Optional[Dict[str, Any]]:
        """
        Executes GetItems request for a specific ASIN against Amazon Creators API.
        """
        if not self.is_enabled():
            return None

        token = self._get_access_token()
        if not token:
            return None

        endpoint = f"https://{self._api_host}/paapi5/getitems"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "x-amz-target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems"
        }

        payload = {
            "ItemIds": [external_product_id],
            "ItemIdType": "ASIN",
            "Marketplace": self._marketplace,
            "PartnerTag": self._partner_tag,
            "PartnerType": "Associates",
            "Resources": [
                "ItemInfo.Title",
                "ItemInfo.ByLineInfo",
                "ItemInfo.ProductInfo",
                "ItemInfo.Classifications",
                "ItemInfo.ExternalIds",
                "Images.Primary.Large",
                "OffersV2.Listings.Price",
                "OffersV2.Listings.Availability",
                "Offers.Listings.Price",
                "ParentASIN"
            ]
        }

        try:
            client = self._get_client()
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("ItemsResult", {}).get("Items", [])
                return items[0] if items else None
            else:
                logger.warning(f"Amazon GetItems returned {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"Amazon GetItems execution failed: {str(e)}")
            return None

    def normalize_listing(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes raw item from Amazon Creators API into standard schema."""
        asin = raw_item.get("ASIN") or ""
        item_info = raw_item.get("ItemInfo", {})
        
        # Title
        title = item_info.get("Title", {}).get("DisplayValue", "")
        
        # Brand & Manufacturer
        by_line = item_info.get("ByLineInfo", {})
        brand = by_line.get("Brand", {}).get("DisplayValue", "")
        manufacturer = by_line.get("Manufacturer", {}).get("DisplayValue", "")
        
        # Product Info / Style Code
        product_info = item_info.get("ProductInfo", {})
        model = product_info.get("ItemPartNumber", {}).get("DisplayValue") or product_info.get("ModelNumber", {}).get("DisplayValue") or ""
        color = product_info.get("Color", {}).get("DisplayValue", "")
        size = product_info.get("Size", {}).get("DisplayValue", "")
        
        # External Identifiers (EAN, UPC, GTIN)
        external_ids = item_info.get("ExternalIds", {})
        eans = external_ids.get("EANs", {}).get("DisplayValues", [])
        upcs = external_ids.get("UPCs", {}).get("DisplayValues", [])
        gtin = eans[0] if eans else (upcs[0] if upcs else None)
        
        # Product Image (Large Primary)
        images = raw_item.get("Images", {})
        primary_large = images.get("Primary", {}).get("Large", {})
        image_url = primary_large.get("URL")
        
        # Detail Page URL with Partner Tag
        detail_url = raw_item.get("DetailPageURL")
        if not detail_url and asin:
            detail_url = f"https://{self._marketplace}/dp/{asin}"
            if self._partner_tag:
                detail_url += f"?tag={self._partner_tag}"

        return {
            "retailer": "amazon",
            "external_product_id": asin,
            "title": title,
            "brand": brand or manufacturer,
            "model": model,
            "style_code": model,
            "color": color,
            "size": size,
            "gtin": gtin,
            "image_url": image_url,
            "product_url": detail_url,
            "raw_item": raw_item
        }

    def normalize_offer(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extracts live observed offer / price from Amazon Creators API payload."""
        # Check OffersV2 first (modern Creators API structure)
        offers_v2 = raw_item.get("OffersV2", {}).get("Listings", [])
        if offers_v2:
            listing = offers_v2[0]
            price_info = listing.get("Price", {})
            amount = price_info.get("Amount")
            currency = price_info.get("Currency", "INR")
            avail = listing.get("Availability", {}).get("Type", "IN_STOCK")
            if amount is not None:
                return {
                    "price": float(amount),
                    "currency": currency,
                    "availability": "IN_STOCK" if "IN_STOCK" in str(avail).upper() else "OUT_OF_STOCK",
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "source": "AMAZON_CREATORS_API"
                }

        # Fallback to standard Offers.Listings
        offers_v1 = raw_item.get("Offers", {}).get("Listings", [])
        if offers_v1:
            listing = offers_v1[0]
            price_info = listing.get("Price", {})
            amount = price_info.get("Amount")
            currency = price_info.get("Currency", "INR")
            avail = listing.get("Availability", {}).get("Message", "In Stock")
            if amount is not None:
                return {
                    "price": float(amount),
                    "currency": currency,
                    "availability": "IN_STOCK" if "in stock" in str(avail).lower() else "OUT_OF_STOCK",
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "source": "AMAZON_CREATORS_API"
                }

        return None

    def verify_identity(
        self,
        canonical_product: Dict[str, Any],
        raw_or_normalized_item: Dict[str, Any]
    ) -> Tuple[bool, str, float, Dict[str, Any]]:
        """
        Evaluates physical identity match according to strict hierarchy:
        1. Exact GTIN / EAN match -> VARIANT_EXACT (1.0)
        2. Manufacturer Style Code + Brand + Compatible Variant -> VARIANT_EXACT (0.98)
        3. Title / Brand alone -> SEARCH_FALLBACK (0.60, unverified)
        """
        if "raw_item" in raw_or_normalized_item:
            norm = raw_or_normalized_item
        else:
            norm = self.normalize_listing(raw_or_normalized_item)

        canon_gtin = (canonical_product.get("gtin") or "").strip()
        cand_gtin = (norm.get("gtin") or "").strip()
        canon_style = (canonical_product.get("style_code") or "").strip().upper()
        cand_style = (norm.get("style_code") or "").strip().upper()
        canon_brand = (canonical_product.get("brand") or "").strip().lower()
        cand_brand = (norm.get("brand") or "").strip().lower()

        # 1. Exact GTIN match
        if canon_gtin and cand_gtin and canon_gtin == cand_gtin:
            evidence = {
                "type": "GTIN_EXACT_MATCH",
                "gtin": canon_gtin,
                "asin": norm.get("external_product_id"),
                "source": "AMAZON_CREATORS_API",
                "verified_at": datetime.now(timezone.utc).isoformat()
            }
            return True, "VARIANT_EXACT", 1.0, evidence

        # 2. Manufacturer Style Code + Brand match
        if (
            canon_style and
            cand_style and
            canon_style == cand_style and
            canon_brand and
            cand_brand and
            (canon_brand in cand_brand or cand_brand in canon_brand)
        ):
            evidence = {
                "type": "MANUFACTURER_STYLE_MATCH",
                "style_code": canon_style,
                "asin": norm.get("external_product_id"),
                "brand": canon_brand,
                "source": "AMAZON_CREATORS_API",
                "verified_at": datetime.now(timezone.utc).isoformat()
            }
            return True, "VARIANT_EXACT", 0.98, evidence

        # 3. If no deterministic identity proof exists -> Not verified
        evidence = {
            "type": "SEARCH_FALLBACK",
            "reason": "Candidate listing lacks exact GTIN or Style Code correspondence"
        }
        return False, "SEARCH_FALLBACK", 0.60, evidence

    def build_search_fallback(self, query: str) -> Dict[str, Any]:
        """Constructs an honest, unverified search fallback card for Amazon India."""
        encoded_q = urllib.parse.quote_plus(query)
        search_url = f"https://{self._marketplace}/s?k={encoded_q}"
        if self._partner_tag:
            search_url += f"&tag={self._partner_tag}"

        return {
            "retailer": "amazon",
            "store_name": self.retailer_name,
            "store_domain": self.domain,
            "store_logo_url": "https://upload.wikimedia.org/wikipedia/commons/a/a9/Amazon_logo.svg",
            "external_product_id": None,
            "external_title": f"Search '{query}' on Amazon India",
            "external_product_image": None,
            "external_image_url": None,
            "external_url": search_url,
            "external_product_url": search_url,
            "price": None,
            "mrp": None,
            "currency": "INR",
            "match_type": "SEARCH_FALLBACK",
            "match_confidence": 0.60,
            "action_label": f"Search on {self.retailer_name} →",
            "identity_evidence": {
                "type": "SEARCH_FALLBACK",
                "reason": "Direct active Amazon India listing unverified"
            },
            "source": "Amazon India Search",
            "observed_at": None
        }

    def resolve_canonical_product_offer(self, canonical_product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes end-to-end resolution for a canonical product:
        1. If connector disabled or credentials missing -> Return Search Fallback.
        2. Query Creators API using GTIN or Style Code or Title.
        3. Match candidate items.
        4. If verified exact match found with price & image -> Return Verified Retailer Offer.
        5. Otherwise -> Return Search Fallback.
        """
        title = canonical_product.get("title") or canonical_product.get("apex_product_name") or "Product"
        style_code = canonical_product.get("style_code")
        gtin = canonical_product.get("gtin")

        if not self.is_enabled():
            query = f"{canonical_product.get('brand', '')} {style_code or title}".strip()
            return self.build_search_fallback(query)

        # Build targeted query
        search_query = gtin or (f"{canonical_product.get('brand', '')} {style_code}".strip() if style_code else title)
        candidates = self.search_products(search_query)

        for cand in candidates:
            norm = self.normalize_listing(cand)
            is_match, match_type, conf, evidence = self.verify_identity(canonical_product, norm)
            
            if is_match and match_type in ["VARIANT_EXACT", "EXACT", "MODEL_EXACT"]:
                offer_data = self.normalize_offer(cand)
                if offer_data and offer_data.get("price") is not None:
                    # Valid verified exact listing with price and authentic image
                    return {
                        "retailer": "amazon",
                        "store_name": self.retailer_name,
                        "store_domain": self.domain,
                        "store_logo_url": "https://upload.wikimedia.org/wikipedia/commons/a/a9/Amazon_logo.svg",
                        "external_product_id": norm.get("external_product_id"),
                        "external_title": norm.get("title"),
                        "external_product_image": norm.get("image_url"),
                        "external_image_url": norm.get("image_url"),
                        "external_url": norm.get("product_url"),
                        "external_product_url": norm.get("product_url"),
                        "price": Decimal(str(offer_data["price"])),
                        "mrp": None,
                        "currency": offer_data.get("currency", "INR"),
                        "brand": norm.get("brand"),
                        "model": norm.get("model"),
                        "style_code": norm.get("style_code"),
                        "gtin": norm.get("gtin"),
                        "match_type": match_type,
                        "match_confidence": conf,
                        "action_label": "View exact product →",
                        "identity_evidence": evidence,
                        "source": "AMAZON_CREATORS_API",
                        "observed_at": offer_data.get("observed_at")
                    }

        # Fallback if no verified candidate met strict requirements
        fallback_query = f"{canonical_product.get('brand', '')} {style_code or title}".strip()
        return self.build_search_fallback(fallback_query)
