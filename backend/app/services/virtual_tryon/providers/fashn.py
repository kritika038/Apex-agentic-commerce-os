import os
import time
import base64
import requests
from typing import Dict, Any, Optional, Tuple
from app.services.virtual_tryon.base import VirtualTryOnProvider

class FashnVirtualTryOnProvider(VirtualTryOnProvider):
    """
    Production Virtual Try-On Provider using FASHN API (tryon-v1.6).
    Performs true generative neural garment transfer with bounded polling,
    output validation, and secure credential handling.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 45,
        poll_interval: float = 1.5,
        max_poll_attempts: int = 30
    ):
        self.api_key = (api_key or os.environ.get("FASHN_API_KEY", "")).strip()
        self.base_url = (base_url or os.environ.get("FASHN_API_BASE_URL", "https://api.fashn.ai/v1")).rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_poll_attempts = max_poll_attempts

    @property
    def provider_id(self) -> str:
        return "fashn"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    @property
    def is_demo(self) -> bool:
        return False

    def _map_category(self, garment_type: str, product_metadata: Dict[str, Any]) -> str:
        subcat = (product_metadata.get("subcategory") or "").lower()
        cat = (product_metadata.get("category") or "").lower()
        name = (product_metadata.get("name") or "").lower()
        combined = f"{subcat} {cat} {name}"

        if any(k in combined for k in ["dress", "jumpsuit", "kurta", "tracksuit", "one-piece", "gown", "romper"]):
            return "one-pieces"
        if any(k in combined for k in ["jean", "jeans", "trouser", "trousers", "pants", "pant", "shorts", "short", "skirt", "skirts", "track pants", "leggings"]):
            return "bottoms"
        return "tops"

    def generate_try_on(
        self,
        person_image_bytes: bytes,
        product_image_url: str,
        garment_type: str,
        product_metadata: Dict[str, Any],
        progress_callback: Optional[Any] = None
    ) -> Tuple[bool, Optional[bytes], Optional[str], Optional[str]]:
        """
        Executes generative AI try-on using FASHN API tryon-v1.6.
        """
        if not self.is_available:
            return (
                False,
                None,
                "PROVIDER_NOT_CONFIGURED",
                "AI Try-On is temporarily unavailable. (FASHN_API_KEY is not configured in backend/.env)"
            )

        if not person_image_bytes or len(person_image_bytes) < 100:
            return (
                False,
                None,
                "INVALID_PERSON_IMAGE",
                "Please capture a clear upper-body photo with good lighting."
            )

        if not product_image_url or not product_image_url.strip():
            return (
                False,
                None,
                "INVALID_GARMENT_IMAGE",
                "Selected apparel item has no valid product visual asset."
            )

        # 1. Format person image as base64 data URI
        mime = "image/jpeg"
        if person_image_bytes.startswith(b"\x89PNG"):
            mime = "image/png"
        elif person_image_bytes.startswith(b"RIFF"):
            mime = "image/webp"

        b64_data = base64.b64encode(person_image_bytes).decode("utf-8")
        model_image_uri = f"data:{mime};base64,{b64_data}"

        category = self._map_category(garment_type, product_metadata)

        # 2. Build FASHN run payload
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model_name": "tryon-v1.6",
            "inputs": {
                "model_image": model_image_uri,
                "garment_image": product_image_url,
                "category": category,
                "output_format": "jpeg",
                "mode": "performance"
            }
        }

        # 3. Submit prediction job
        try:
            run_url = f"{self.base_url}/run"
            resp = requests.post(run_url, json=payload, headers=headers, timeout=self.timeout)

            if resp.status_code in [401, 403]:
                return (
                    False,
                    None,
                    "FASHN_AUTH_ERROR",
                    "FASHN API authentication failed. Please verify FASHN_API_KEY."
                )
            if resp.status_code == 429:
                return (
                    False,
                    None,
                    "RATE_LIMIT_EXCEEDED",
                    "Virtual try-on service is experiencing high traffic. Please try again in a moment."
                )
            if resp.status_code >= 400:
                return (
                    False,
                    None,
                    f"FASHN_HTTP_{resp.status_code}",
                    f"FASHN API returned an error: {resp.text[:150]}"
                )

            run_data = resp.json()
            prediction_id = run_data.get("id")
            if not prediction_id:
                return (
                    False,
                    None,
                    "FASHN_INVALID_RESPONSE",
                    "FASHN API did not return a valid prediction ID."
                )

            # Check if immediately completed
            if run_data.get("status") == "completed" and run_data.get("output"):
                return self._download_and_validate_output(run_data["output"][0], person_image_bytes)

        except requests.Timeout:
            return (
                False,
                None,
                "PROVIDER_TIMEOUT",
                "Try-On submission timed out. Please try again."
            )
        except Exception as e:
            return (
                False,
                None,
                "FASHN_CONNECTION_ERROR",
                f"Failed to connect to FASHN API: {str(e)}"
            )

        # 4. Status Polling Loop
        status_url = f"{self.base_url}/status/{prediction_id}"
        attempts = 0

        while attempts < self.max_poll_attempts:
            attempts += 1
            time.sleep(self.poll_interval)

            try:
                poll_resp = requests.get(status_url, headers=headers, timeout=15)
                if poll_resp.status_code == 200:
                    status_data = poll_resp.json()
                    status = status_data.get("status")

                    if status == "completed":
                        outputs = status_data.get("output") or []
                        if not outputs or not outputs[0]:
                            return (
                                False,
                                None,
                                "EMPTY_OUTPUT",
                                "FASHN AI completed but produced an empty output list."
                            )
                        return self._download_and_validate_output(outputs[0], person_image_bytes)

                    elif status == "failed":
                        err_detail = status_data.get("error")
                        err_msg = (
                            err_detail.get("message")
                            if isinstance(err_detail, dict)
                            else str(err_detail or "AI garment synthesis failed.")
                        )
                        return (
                            False,
                            None,
                            "FASHN_SYNTHESIS_FAILED",
                            f"Virtual try-on synthesis failed: {err_msg}"
                        )

                    # Continue polling for starting / in_progress
                elif poll_resp.status_code in [401, 403]:
                    return (
                        False,
                        None,
                        "FASHN_AUTH_ERROR",
                        "FASHN API authentication expired during polling."
                    )
            except requests.Timeout:
                continue
            except Exception as e:
                return (
                    False,
                    None,
                    "POLLING_ERROR",
                    f"Error polling try-on status: {str(e)}"
                )

        return (
            False,
            None,
            "PROVIDER_TIMEOUT",
            "Try-On is taking longer than expected. Please try again."
        )

    def _download_and_validate_output(
        self,
        output_url: str,
        input_bytes: bytes
    ) -> Tuple[bool, Optional[bytes], Optional[str], Optional[str]]:
        try:
            dl_resp = requests.get(output_url, timeout=20)
            if dl_resp.status_code != 200:
                return (
                    False,
                    None,
                    "OUTPUT_DOWNLOAD_FAILED",
                    f"Failed to retrieve synthesized try-on image (HTTP {dl_resp.status_code})."
                )

            out_bytes = dl_resp.content
            if len(out_bytes) < 500:
                return (
                    False,
                    None,
                    "INVALID_OUTPUT_IMAGE",
                    "Synthesized image output is corrupted or incomplete."
                )

            # Reject output if byte-identical to original person image
            if out_bytes == input_bytes:
                return (
                    False,
                    None,
                    "IDENTICAL_OUTPUT_REJECTED",
                    "Virtual try-on model returned an unmodified input photo."
                )

            return True, out_bytes, None, None

        except Exception as e:
            return (
                False,
                None,
                "OUTPUT_DOWNLOAD_ERROR",
                f"Failed to download synthesized result: {str(e)}"
            )
