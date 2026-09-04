import os
import json
import time
import base64
import logging
import requests
import uuid
from typing import Dict, Any, Optional, Tuple, List
from app.core.config import settings
from app.services.virtual_tryon.base import VirtualTryOnProvider

logger = logging.getLogger(__name__)

class HuggingFaceZeroGPUProvider(VirtualTryOnProvider):
    """
    Production Virtual Try-On Provider using Hugging Face ZeroGPU Space (kritika68/apex-vton).
    Directly interfaces with open-source fashn-ai/fashn-vton-1.5 via Gradio SSE protocol.
    Completely free of charge and requires no third-party paid API keys.
    """

    def __init__(
        self,
        space_url: Optional[str] = None,
        hf_token: Optional[str] = None,
        timeout: int = 180,
        num_timesteps: int = 20,
        guidance_scale: float = 1.5,
    ):
        self._space_url = space_url
        self._hf_token = hf_token
        self.timeout = timeout
        self.num_timesteps = num_timesteps
        self.guidance_scale = guidance_scale

    @property
    def space_url(self) -> str:
        if self._space_url is not None:
            return self._space_url.strip().rstrip("/")
        env_url = os.environ.get("VTO_HF_SPACE_URL") or getattr(settings, "VTO_HF_SPACE_URL", "https://kritika68-apex-vton.hf.space")
        return env_url.strip().rstrip("/")

    @property
    def hf_token(self) -> Optional[str]:
        if self._hf_token is not None and self._hf_token.strip():
            return self._hf_token.strip()
        tok = os.environ.get("HF_TOKEN") or getattr(settings, "HF_TOKEN", "")
        return tok.strip() if tok else None

    @property
    def provider_id(self) -> str:
        return "huggingface_zerogpu"

    @property
    def is_available(self) -> bool:
        return bool(self.space_url)

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

    def _upload_file_bytes(self, file_bytes: bytes, filename: str, mime_type: str = "image/jpeg") -> Optional[str]:
        """
        Uploads image bytes directly to the Gradio /gradio_api/upload endpoint.
        Returns the server-side temporary file path.
        """
        upload_url = f"{self.space_url}/gradio_api/upload"
        headers = {}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"

        files = {
            "files": (filename, file_bytes, mime_type)
        }
        try:
            resp = requests.post(upload_url, files=files, headers=headers, timeout=40)
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0]
            logger.warning(f"Gradio file upload failed HTTP {resp.status_code}: {resp.text[:150]}")
            return None
        except Exception as e:
            logger.error(f"Exception uploading file to HF space: {e}")
            return None

    def _fetch_garment_bytes(self, product_image_url: str) -> Optional[bytes]:
        """Fetches remote garment image bytes safely with timeout and size check."""
        try:
            resp = requests.get(product_image_url, timeout=15, headers={"User-Agent": "Apex-Commerce-OS/1.0"})
            if resp.status_code == 200 and len(resp.content) >= 100:
                return resp.content
            return None
        except Exception as e:
            logger.warning(f"Failed to download garment image from URL {product_image_url}: {e}")
            return None

    def generate_try_on(
        self,
        person_image_bytes: bytes,
        product_image_url: str,
        garment_type: str,
        product_metadata: Dict[str, Any],
        progress_callback: Optional[Any] = None
    ) -> Tuple[bool, Optional[bytes], Optional[str], Optional[str]]:
        """
        Executes generative neural try-on via Hugging Face ZeroGPU Space running FASHN VTON v1.5.
        """
        if not self.is_available:
            return (
                False,
                None,
                "HF_SPACE_UNAVAILABLE",
                "Hugging Face ZeroGPU Space endpoint URL is not configured."
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

        # Stage 1: PREPARING
        if progress_callback:
            progress_callback("PREPARING", 10, None, None, "Preparing model and garment assets...")

        garment_bytes = self._fetch_garment_bytes(product_image_url)
        if not garment_bytes:
            return (
                False,
                None,
                "GARMENT_DOWNLOAD_FAILED",
                "Failed to load garment image visual asset."
            )

        # Stage 2: GARMENT_VALIDATION & POSE_DETECTION
        if progress_callback:
            progress_callback("GARMENT_VALIDATION", 20, None, None, "Validating garment geometry...")

        # Determine MIME types
        person_mime = "image/png" if person_image_bytes.startswith(b"\x89PNG") else "image/jpeg"
        garment_mime = "image/png" if garment_bytes.startswith(b"\x89PNG") else "image/jpeg"

        # Upload files to Gradio Space
        person_remote_path = self._upload_file_bytes(person_image_bytes, f"person_{uuid.uuid4().hex[:8]}.jpg", person_mime)
        garment_remote_path = self._upload_file_bytes(garment_bytes, f"garment_{uuid.uuid4().hex[:8]}.jpg", garment_mime)

        if not person_remote_path or not garment_remote_path:
            return (
                False,
                None,
                "ASSET_UPLOAD_FAILED",
                "AI Try-On is temporarily busy. Please try again."
            )

        if progress_callback:
            progress_callback("GARMENT_PREPARATION", 35, None, None, "Submitting to Hugging Face ZeroGPU cluster...")

        category = self._map_category(garment_type, product_metadata)

        # Build payload for /gradio_api/call/tryon
        headers = {"Content-Type": "application/json"}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"

        payload = {
            "data": [
                {"path": person_remote_path, "meta": {"_type": "gradio.FileData"}},
                {"path": garment_remote_path, "meta": {"_type": "gradio.FileData"}},
                category,
                self.num_timesteps,
                self.guidance_scale,
                "flat-lay"
            ]
        }

        call_url = f"{self.space_url}/gradio_api/call/tryon"
        try:
            resp = requests.post(call_url, json=payload, headers=headers, timeout=45)
            if resp.status_code != 200:
                logger.warning(f"Call to /gradio_api/call/tryon failed: HTTP {resp.status_code} - {resp.text[:200]}")
                return (
                    False,
                    None,
                    f"HF_HTTP_{resp.status_code}",
                    "AI Try-On is temporarily busy. Please try again."
                )

            res_json = resp.json()
            event_id = res_json.get("event_id")
            if not event_id:
                return (
                    False,
                    None,
                    "HF_NO_EVENT_ID",
                    "AI Try-On is temporarily busy. Please try again."
                )

        except requests.Timeout:
            return (
                False,
                None,
                "HF_CALL_TIMEOUT",
                "AI Try-On request timed out while connecting to ZeroGPU."
            )
        except Exception as e:
            logger.error(f"Error calling HF ZeroGPU tryon endpoint: {e}")
            return (
                False,
                None,
                "HF_CONNECTION_ERROR",
                "AI Try-On is temporarily busy. Please try again."
            )

        # Stage 3 & 4: DIFFUSION & Status Polling via SSE Stream
        stream_url = f"{self.space_url}/gradio_api/call/tryon/{event_id}"
        if progress_callback:
            progress_callback("DIFFUSION", 50, 1, self.num_timesteps, f"ZeroGPU Neural Diffusion in progress (category: {category})...")

        try:
            stream_resp = requests.get(stream_url, headers=headers, stream=True, timeout=self.timeout)
            if stream_resp.status_code != 200:
                return (
                    False,
                    None,
                    f"HF_STREAM_HTTP_{stream_resp.status_code}",
                    "AI Try-On is temporarily busy. Please try again."
                )

            current_event = None
            for raw_line in stream_resp.iter_lines():
                if not raw_line:
                    continue
                if isinstance(raw_line, bytes):
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                else:
                    line = str(raw_line).strip()
                if not line:
                    continue

                if line.startswith("event:"):
                    current_event = line.replace("event:", "").strip()
                elif line.startswith("data:"):
                    raw_data = line.replace("data:", "").strip()
                    try:
                        data_json = json.loads(raw_data)
                    except Exception:
                        data_json = raw_data

                    if current_event == "error":
                        err_str = str(data_json)
                        logger.warning(f"HF ZeroGPU error event: {err_str}")
                        if "quota" in err_str.lower() or "busy" in err_str.lower() or "exceeded" in err_str.lower():
                            return (
                                False,
                                None,
                                "ZEROGPU_BUSY",
                                "AI Try-On is temporarily busy. Please try again."
                            )
                        return (
                            False,
                            None,
                            "HF_INFERENCE_ERROR",
                            "AI Try-On is temporarily busy. Please try again."
                        )

                    elif current_event == "generating" or current_event == "heartbeat":
                        if progress_callback:
                            progress_callback("DIFFUSION", 75, 15, self.num_timesteps, "Synthesizing garment details on ZeroGPU...")

                    elif current_event == "complete":
                        if progress_callback:
                            progress_callback("FINALIZING", 95, None, None, "Finalizing high-resolution try-on preview...")

                        # Output data format: [ { "path": "...", "url": "..." }, "status_text" ]
                        if isinstance(data_json, list) and len(data_json) > 0:
                            img_info = data_json[0]
                            output_bytes = self._download_result_image(img_info)
                            if output_bytes:
                                # Validate non-identical image
                                if output_bytes == person_image_bytes:
                                    return (
                                        False,
                                        None,
                                        "IDENTICAL_OUTPUT_REJECTED",
                                        "Virtual try-on returned an unmodified input photo."
                                    )
                                if len(output_bytes) < 100:
                                    return (
                                        False,
                                        None,
                                        "INVALID_OUTPUT_IMAGE",
                                        "Synthesized try-on image was incomplete."
                                    )

                                if progress_callback:
                                    progress_callback("COMPLETED", 100, None, None, "Virtual try-on ready!")
                                return True, output_bytes, None, None

                        return (
                            False,
                            None,
                            "EMPTY_OUTPUT",
                            "FASHN VTON completed but generated an empty visual asset."
                        )

            return (
                False,
                None,
                "STREAM_CLOSED_PREMATURELY",
                "AI Try-On is temporarily busy. Please try again."
            )

        except requests.Timeout:
            return (
                False,
                None,
                "DIFFUSION_TIMEOUT",
                "Virtual try-on synthesis timed out. Please try again."
            )
        except Exception as e:
            logger.error(f"Error reading SSE stream from HF ZeroGPU: {e}")
            return (
                False,
                None,
                "STREAM_ERROR",
                "AI Try-On is temporarily busy. Please try again."
            )

    def _download_result_image(self, img_info: Any) -> Optional[bytes]:
        """Downloads the completed image from Gradio file URL or file path."""
        try:
            if isinstance(img_info, dict):
                url = img_info.get("url")
                path = img_info.get("path")
            elif isinstance(img_info, str):
                url = img_info if img_info.startswith("http") else None
                path = img_info
            else:
                return None

            download_urls = []
            if url:
                download_urls.append(url)
            if path:
                # Gradio file streaming endpoint
                download_urls.append(f"{self.space_url}/gradio_api/file={path}")

            headers = {}
            if self.hf_token:
                headers["Authorization"] = f"Bearer {self.hf_token}"

            for dl_url in download_urls:
                try:
                    resp = requests.get(dl_url, headers=headers, timeout=30)
                    if resp.status_code == 200 and len(resp.content) >= 100:
                        return resp.content
                except Exception as ex:
                    logger.warning(f"Failed to download from {dl_url}: {ex}")

            return None
        except Exception as e:
            logger.error(f"Error downloading result image: {e}")
            return None
