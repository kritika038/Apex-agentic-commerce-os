"""
Product Image Validation & Normalization Service.
Validates, normalizes, and sanitizes image URLs across catalog ingestion, product creation, and offer indexing.
"""

import re
from urllib.parse import urlparse
from typing import Optional, Dict, Any, Tuple


VALID_SCHEMES = {"http", "https", "data"}
TRUSTED_IMAGE_HOSTS = {
    "images.unsplash.com",
    "static.nike.com",
    "assets.adidas.com",
    "m.media-amazon.com",
    "rukminim2.flixcart.com",
    "cdn.superkicks.in",
    "cdn.shopify.com",
    "images.example.com",
    "localsportshub.in",
    "assets.myntassets.com",
    "img.test",
}


def normalize_image_url(url: Optional[str]) -> Optional[str]:
    """
    Cleans and normalizes an image URL string.
    Trims whitespace, strips invalid characters, and validates basic structure.
    """
    if not url or not isinstance(url, str):
        return None

    cleaned = url.strip()
    if not cleaned:
        return None

    # Handle data URIs
    if cleaned.startswith("data:image/"):
        return cleaned

    # Check parseable URL
    try:
        parsed = urlparse(cleaned)
        if not parsed.scheme or parsed.scheme.lower() not in {"http", "https"}:
            return None
        if not parsed.netloc:
            return None
        
        # Normalize protocol to lowercase
        normalized = f"{parsed.scheme.lower()}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized
    except Exception:
        return None


def validate_image_url_syntax(url: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validates the syntax and safety of an image URL.
    Returns (is_valid, error_reason).
    """
    if not url:
        return True, None  # Optional image URLs are permissible

    if not isinstance(url, str):
        return False, "Image URL must be a string."

    trimmed = url.strip()
    if not trimmed:
        return True, None

    if trimmed.startswith("data:image/"):
        if re.match(r"^data:image\/(png|jpeg|jpg|webp|svg\+xml);base64,[A-Za-z0-9+/=]+$", trimmed) or trimmed.startswith("data:image/svg+xml;utf8,"):
            return True, None
        return False, "Invalid image data URI format."

    try:
        parsed = urlparse(trimmed)
        if parsed.scheme.lower() not in {"http", "https"}:
            return False, f"Unsupported URL scheme: {parsed.scheme}. Only HTTP/HTTPS or data URIs are permitted."
        if not parsed.netloc:
            return False, "Missing hostname in image URL."
        return True, None
    except Exception as e:
        return False, f"Malformed image URL: {str(e)}"
