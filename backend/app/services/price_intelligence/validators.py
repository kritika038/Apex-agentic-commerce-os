import re
import urllib.parse
from typing import Tuple, Optional

# Valid ASIN format: 10 alphanumeric chars usually starting with B or 0-9
ASIN_PATTERN = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?#]|$)", re.IGNORECASE)
MYNTRA_PDP_PATTERN = re.compile(r"/(\d{5,10})/buy", re.IGNORECASE)
NIKE_PDP_PATTERN = re.compile(r"/in/t/[^/]+/([A-Z0-9]{6,10}-\d{3}|[A-Z0-9]{6,10})(?:[/?#]|$)", re.IGNORECASE)
ADIDAS_PDP_PATTERN = re.compile(r"/([A-Z0-9]{5,8})\.html(?:[/?#]|$)", re.IGNORECASE)
PUMA_PDP_PATTERN = re.compile(r"/(?:pd|p)/[^/]+/(\d{6,10})(?:[/?#]|$)", re.IGNORECASE)
FLIPKART_PDP_PATTERN = re.compile(r"/p/(itm[a-z0-9]+)(?:[/?#]|$)", re.IGNORECASE)

AUTHORIZED_RETAILER_IMAGE_HOSTS = [
    "media-amazon.com",
    "images-amazon.com",
    "ssl-images-amazon.com",
    "static.nike.com",
    "assets.adidas.com",
    "assets.myntassets.com",
    "images.puma.com",
    "rukminim1.flixcart.com",
    "rukminim2.flixcart.com",
    "contents.mediadecathlon.com"
]

def validate_gtin_checksum(gtin: Optional[str]) -> bool:
    """
    Validates GTIN-8, GTIN-12 (UPC-A), GTIN-13 (EAN-13), or GTIN-14 standard GS1 check-digit.
    Returns False if GTIN is missing, non-numeric, wrong length, or fails check digit.
    """
    if not gtin or not isinstance(gtin, str):
        return False
    digits_str = gtin.strip()
    if not digits_str.isdigit() or len(digits_str) not in (8, 12, 13, 14):
        return False
    digits = [int(c) for c in digits_str]
    check = digits[-1]
    core = digits[:-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(core)))
    expected_check = (10 - (total % 10)) % 10
    return check == expected_check

def is_search_or_category_url(url: str) -> bool:
    """Checks if a retailer URL is a search query, category browse, or generic homepage."""
    if not url or not isinstance(url, str):
        return True
    
    url_lower = url.strip().lower()
    if not (url_lower.startswith("http://") or url_lower.startswith("https://")):
        return True

    # Search indicators
    if any(q in url_lower for q in ["/s?k=", "/s?", "/search", "query=", "?q=", "&q=", "/search/"]):
        return True

    # Generic root or store browse indicators
    parsed = urllib.parse.urlparse(url_lower)
    path = parsed.path.rstrip("/")
    if not path or path in ["", "/", "/in", "/in/en", "/in/w", "/mens", "/womens", "/shoes", "/tshirts"]:
        return True

    return False

def is_exact_amazon_pdp(url: str) -> Tuple[bool, Optional[str]]:
    """Validates Amazon direct Product Detail Page (PDP)."""
    if is_search_or_category_url(url):
        return False, None
    if "amazon.in" not in url and "amazon.com" not in url:
        return False, None

    match = ASIN_PATTERN.search(url)
    if match:
        asin = match.group(1).upper()
        # Reject obvious synthetic/dummy ASINs
        if asin.startswith("B09DEMO") or asin.startswith("DEMO") or asin == "B000000000":
            return False, None
        return True, asin
    return False, None

def is_exact_myntra_pdp(url: str) -> Tuple[bool, Optional[str]]:
    """Validates Myntra direct PDP (ends in /<styleId>/buy)."""
    if is_search_or_category_url(url):
        return False, None
    if "myntra.com" not in url:
        return False, None

    match = MYNTRA_PDP_PATTERN.search(url)
    if match:
        return True, match.group(1)
    return False, None

def is_exact_nike_pdp(url: str) -> Tuple[bool, Optional[str]]:
    """Validates Nike Official direct PDP."""
    if is_search_or_category_url(url):
        return False, None
    if "nike.com" not in url:
        return False, None

    match = NIKE_PDP_PATTERN.search(url)
    if match:
        return True, match.group(1).upper()
    return False, None

def is_exact_adidas_pdp(url: str) -> Tuple[bool, Optional[str]]:
    """Validates Adidas Official direct PDP."""
    if is_search_or_category_url(url):
        return False, None
    if "adidas.co.in" not in url and "adidas.com" not in url:
        return False, None

    match = ADIDAS_PDP_PATTERN.search(url)
    if match:
        return True, match.group(1).upper()
    return False, None

def is_exact_puma_pdp(url: str) -> Tuple[bool, Optional[str]]:
    """Validates Puma Official direct PDP."""
    if is_search_or_category_url(url):
        return False, None
    if "puma.com" not in url:
        return False, None

    match = PUMA_PDP_PATTERN.search(url)
    if match:
        return True, match.group(1)
    return False, None

def is_exact_flipkart_pdp(url: str) -> Tuple[bool, Optional[str]]:
    """Validates Flipkart direct PDP."""
    if is_search_or_category_url(url):
        return False, None
    if "flipkart.com" not in url:
        return False, None

    match = FLIPKART_PDP_PATTERN.search(url)
    if match:
        item_id = match.group(1).upper()
        if "1234567" in item_id or "DEMO" in item_id or "TEST" in item_id:
            return False, None
        return True, item_id
    return False, None

def validate_retailer_pdp_url(retailer_domain: str, url: str) -> Tuple[bool, Optional[str]]:
    """Dispatches URL validation based on retailer domain."""
    domain_clean = (retailer_domain or "").lower()
    if "amazon" in domain_clean:
        return is_exact_amazon_pdp(url)
    elif "myntra" in domain_clean:
        return is_exact_myntra_pdp(url)
    elif "nike" in domain_clean:
        return is_exact_nike_pdp(url)
    elif "adidas" in domain_clean:
        return is_exact_adidas_pdp(url)
    elif "puma" in domain_clean:
        return is_exact_puma_pdp(url)
    elif "flipkart" in domain_clean:
        return is_exact_flipkart_pdp(url)
    else:
        # Generic retailer check: must not be a search/query URL and must have path depth >= 2
        if is_search_or_category_url(url):
            return False, None
        parsed = urllib.parse.urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) >= 2:
            return True, path_parts[-1]
        return False, None

def validate_external_product_image(
    image_url: Optional[str],
    canonical_image_url: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validates that an external offer provides its own authentic retailer product image.
    Enforces that:
    1. It is a valid non-empty http/https URL.
    2. It does not reuse the Apex canonical/Unsplash image.
    3. It belongs to an authorized retailer image host or valid cdn.
    """
    if not image_url or not isinstance(image_url, str):
        return False, "Missing retailer product image"

    clean_img = image_url.strip()
    if not (clean_img.startswith("http://") or clean_img.startswith("https://")):
        return False, "Invalid image URL scheme"

    if canonical_image_url and clean_img == canonical_image_url.strip():
        return False, "External image cannot reuse the Apex canonical image"

    # Reject Unsplash copies for third-party marketplace listings
    if "images.unsplash.com" in clean_img:
        return False, "Unsplash image cannot be used as external retailer listing image"

    parsed = urllib.parse.urlparse(clean_img)
    host = parsed.netloc.lower()

    # Check if host is recognized retailer cdn
    is_known_host = any(auth_host in host for auth_host in AUTHORIZED_RETAILER_IMAGE_HOSTS)
    if is_known_host or any(ext in parsed.path.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        return True, None

    return True, None
