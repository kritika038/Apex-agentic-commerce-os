import os
import requests
from typing import Dict, Any, Optional, Tuple
from app.services.virtual_tryon.base import VirtualTryOnProvider

class GenericApiVirtualTryOnProvider(VirtualTryOnProvider):
    """
    Configurable Production Virtual Try-On Provider connecting to external REST/diffusion endpoints.
    Reads credentials strictly from backend server environment variables.
    """

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 30):
        self.api_url = api_url or os.environ.get("VIRTUAL_TRYON_API_URL", "")
        self.api_key = api_key or os.environ.get("VIRTUAL_TRYON_API_KEY", "")
        self.timeout = timeout or int(os.environ.get("VIRTUAL_TRYON_TIMEOUT_SECONDS", "30"))

    @property
    def provider_id(self) -> str:
        return "api_provider"

    @property
    def is_available(self) -> bool:
        return bool(self.api_url and self.api_key)

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
        if not self.is_available:
            return False, None, "PROVIDER_NOT_CONFIGURED", "Production Virtual Try-On API endpoint or API key is not configured."

        try:
            files = {
                "person_image": ("person.jpg", person_image_bytes, "image/jpeg"),
            }
            data = {
                "product_image_url": product_image_url,
                "garment_type": garment_type,
                "product_metadata": str(product_metadata)
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }

            resp = requests.post(self.api_url, files=files, data=data, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                return True, resp.content, None, None
            else:
                return False, None, f"HTTP_{resp.status_code}", f"VTO API returned status {resp.status_code}: {resp.text[:200]}"

        except requests.Timeout:
            return False, None, "PROVIDER_TIMEOUT", "Virtual Try-On generation timed out. Please try again."
        except Exception as e:
            return False, None, "PROVIDER_REQUEST_FAILED", f"Failed to contact VTO provider: {str(e)}"
