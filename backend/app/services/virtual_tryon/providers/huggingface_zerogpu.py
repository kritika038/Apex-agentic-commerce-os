import os
import json
import time
import base64
import logging
import requests
import uuid
import hashlib
import threading
from typing import Dict, Any, Optional, Tuple, List
from app.core.config import settings
from app.services.virtual_tryon.base import VirtualTryOnProvider

logger = logging.getLogger(__name__)

class HuggingFaceZeroGPUProvider(VirtualTryOnProvider):
    """
    Hardened Production Virtual Try-On Provider using Hugging Face ZeroGPU Space (kritika68/apex-vton).
    Directly interfaces with open-source fashn-ai/fashn-vton-1.5 via Gradio SSE protocol.
    Completely free of charge, privacy-safe, with zero-leak diagnostic logging and fine-grained
    error classification.
    """

    _inflight_lock = threading.Lock()
    _inflight_hashes = set()

    def __init__(
        self,
        space_url: Optional[str] = None,
        hf_token: Optional[str] = None,
        timeout: int = 120,
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

    def _get_headers(self, json_content: bool = False) -> Dict[str, str]:
        headers = {
            "User-Agent": "Apex-Agentic-Commerce-OS/1.0",
        }
        if json_content:
            headers["Content-Type"] = "application/json"
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        return headers

    def _upload_file_bytes(self, file_bytes: bytes, filename: str, mime_type: str = "image/jpeg") -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Uploads image bytes directly to Gradio /gradio_api/upload endpoint.
        Returns (remote_path, error_code, user_error_message).
        """
        upload_url = f"{self.space_url}/gradio_api/upload"
        headers = self._get_headers(json_content=False)

        files = {
            "files": (filename, file_bytes, mime_type)
        }
        try:
            resp = requests.post(upload_url, files=files, headers=headers, timeout=35)
            logger.info(f"[HF_VTO_DIAGNOSTICS] action=upload endpoint={self.space_url}/gradio_api/upload status={resp.status_code}")

            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0], None, None
                return None, "MALFORMED_UPLOAD_RESPONSE", "AI Try-On received an unexpected upload response from the Space."
            elif resp.status_code == 429:
                return None, "HTTP_429_RATE_LIMIT", "AI Try-On is receiving high traffic. Please try again shortly."
            elif resp.status_code in [502, 503, 504]:
                return None, "SPACE_SLEEPING_OR_RESTARTING", "AI Try-On is temporarily unavailable."
            elif resp.status_code >= 500:
                return None, "HTTP_5XX_SERVER_ERROR", "AI Try-On is temporarily unavailable."
            else:
                return None, f"HF_UPLOAD_HTTP_{resp.status_code}", "AI Try-On is temporarily unavailable."
        except requests.Timeout:
            logger.warning(f"[HF_VTO_DIAGNOSTICS] action=upload status=TIMEOUT endpoint={upload_url}")
            return None, "INFERENCE_TIMEOUT", "AI Try-On request timed out while uploading visual assets."
        except Exception as e:
            logger.error(f"[HF_VTO_DIAGNOSTICS] action=upload status=EXCEPTION err_class={type(e).__name__}")
            return None, "SPACE_UNAVAILABLE", "AI Try-On is temporarily unavailable."

    def _fetch_garment_bytes(self, product_image_url: str) -> Optional[bytes]:
        """Fetches remote garment image bytes safely with timeout and size check."""
        try:
            resp = requests.get(product_image_url, timeout=15, headers={"User-Agent": "Apex-Commerce-OS/1.0"})
            if resp.status_code == 200 and len(resp.content) >= 100:
                return resp.content
            return None
        except Exception as e:
            logger.warning(f"[HF_VTO_DIAGNOSTICS] action=fetch_garment status=FAILED err_class={type(e).__name__}")
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
        Distinguishes:
          - ZEROGPU_QUOTA_EXHAUSTED
          - ZEROGPU_BUSY
          - SPACE_SLEEPING_OR_RESTARTING
          - SPACE_RUNTIME_ERROR
          - HTTP_429_RATE_LIMIT
          - HTTP_5XX_SERVER_ERROR
          - INFERENCE_TIMEOUT
          - MALFORMED_RESPONSE
          - SUCCESS
        """
        if not self.is_available:
            return (
                False,
                None,
                "CONFIGURATION_ERROR",
                "AI Try-On configuration error."
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

        # Idempotency / Single in-flight execution check
        req_hash = hashlib.sha256(person_image_bytes[:1024] + product_image_url.encode()).hexdigest()
        with self._inflight_lock:
            if req_hash in self._inflight_hashes:
                logger.warning(f"[HF_VTO_DIAGNOSTICS] action=duplicate_request_blocked hash={req_hash[:12]}")
                return (
                    False,
                    None,
                    "DUPLICATE_REQUEST_BLOCKED",
                    "A virtual try-on request for this item is already in progress."
                )
            self._inflight_hashes.add(req_hash)

        try:
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

            # Stage 2: GARMENT_VALIDATION & UPLOAD
            if progress_callback:
                progress_callback("GARMENT_VALIDATION", 20, None, None, "Validating garment geometry...")

            person_mime = "image/png" if person_image_bytes.startswith(b"\x89PNG") else "image/jpeg"
            garment_mime = "image/png" if garment_bytes.startswith(b"\x89PNG") else "image/jpeg"

            person_remote_path, up_err_code, up_err_msg = self._upload_file_bytes(
                person_image_bytes, f"person_{uuid.uuid4().hex[:8]}.jpg", person_mime
            )
            if not person_remote_path:
                return False, None, up_err_code or "ASSET_UPLOAD_FAILED", up_err_msg or "AI Try-On is temporarily unavailable."

            garment_remote_path, up_err_code2, up_err_msg2 = self._upload_file_bytes(
                garment_bytes, f"garment_{uuid.uuid4().hex[:8]}.jpg", garment_mime
            )
            if not garment_remote_path:
                return False, None, up_err_code2 or "ASSET_UPLOAD_FAILED", up_err_msg2 or "AI Try-On is temporarily unavailable."

            if progress_callback:
                progress_callback("GARMENT_PREPARATION", 35, None, None, "Submitting to Hugging Face ZeroGPU cluster...")

            category = self._map_category(garment_type, product_metadata)

            # Build payload for /gradio_api/call/tryon
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
            headers = self._get_headers(json_content=True)

            # Submit call (at most 1 safe retry for initial network glitch ONLY if event_id was not received)
            event_id = None
            max_attempts = 2
            for attempt in range(1, max_attempts + 1):
                try:
                    resp = requests.post(call_url, json=payload, headers=headers, timeout=30)
                    logger.info(f"[HF_VTO_DIAGNOSTICS] action=call_tryon attempt={attempt} status={resp.status_code} endpoint={call_url}")

                    if resp.status_code == 200:
                        res_json = resp.json()
                        event_id = res_json.get("event_id")
                        if event_id:
                            break
                        else:
                            return (
                                False,
                                None,
                                "MALFORMED_RESPONSE",
                                "AI Try-On received an unexpected response from the GPU cluster."
                            )
                    elif resp.status_code == 429:
                        return (
                            False,
                            None,
                            "HTTP_429_RATE_LIMIT",
                            "AI Try-On is receiving high traffic. Please try again shortly."
                        )
                    elif resp.status_code in [502, 503, 504]:
                        if attempt == max_attempts:
                            return (
                                False,
                                None,
                                "SPACE_SLEEPING_OR_RESTARTING",
                                "AI Try-On is temporarily unavailable."
                            )
                        time.sleep(1)
                    else:
                        return (
                            False,
                            None,
                            f"HTTP_{resp.status_code}",
                            "AI Try-On is temporarily unavailable."
                        )
                except requests.Timeout:
                    logger.warning(f"[HF_VTO_DIAGNOSTICS] action=call_tryon attempt={attempt} status=TIMEOUT")
                    if attempt == max_attempts:
                        return (
                            False,
                            None,
                            "INFERENCE_TIMEOUT",
                            "AI Try-On request timed out while connecting to ZeroGPU."
                        )
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"[HF_VTO_DIAGNOSTICS] action=call_tryon attempt={attempt} err_class={type(e).__name__}")
                    if attempt == max_attempts:
                        return (
                            False,
                            None,
                            "SPACE_UNAVAILABLE",
                            "AI Try-On is temporarily unavailable."
                        )
                    time.sleep(1)

            if not event_id:
                return (
                    False,
                    None,
                    "SPACE_UNAVAILABLE",
                    "AI Try-On is temporarily unavailable."
                )

            # Stage 3 & 4: DIFFUSION & Status Polling via SSE Stream (NO RETRY ONCE IN QUEUE)
            stream_url = f"{self.space_url}/gradio_api/call/tryon/{event_id}"
            logger.info(f"[HF_VTO_DIAGNOSTICS] action=stream_sse event_id={event_id} status=CONNECTED")
            if progress_callback:
                progress_callback("DIFFUSION", 50, 1, self.num_timesteps, f"ZeroGPU Neural Diffusion in progress (category: {category})...")

            try:
                stream_resp = requests.get(stream_url, headers=headers, stream=True, timeout=self.timeout)
                if stream_resp.status_code == 429:
                    return False, None, "HTTP_429_RATE_LIMIT", "AI Try-On is receiving high traffic. Please try again shortly."
                elif stream_resp.status_code in [502, 503, 504]:
                    return False, None, "SPACE_SLEEPING_OR_RESTARTING", "AI Try-On is temporarily unavailable."
                elif stream_resp.status_code != 200:
                    return False, None, f"HTTP_{stream_resp.status_code}", "AI Try-On is temporarily unavailable."

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
                            err_str = str(data_json).lower()
                            logger.info(f"[HF_VTO_DIAGNOSTICS] action=sse_error event_id={event_id} err_preview={err_str[:120]}")

                            if any(k in err_str for k in ["quota", "exceeded your zerogpu quota", "quota exceeded", "try again in"]):
                                return (
                                    False,
                                    None,
                                    "ZEROGPU_QUOTA_EXHAUSTED",
                                    "AI Try-On has reached today's free GPU limit. Please try again later."
                                )
                            elif any(k in err_str for k in ["busy", "queue", "gpu allocation", "waiting for gpu", "all gpus"]):
                                return (
                                    False,
                                    None,
                                    "ZEROGPU_BUSY",
                                    "AI Try-On is temporarily busy. Please try again."
                                )
                            elif any(k in err_str for k in ["runtime", "exception", "traceback", "torch"]):
                                return (
                                    False,
                                    None,
                                    "SPACE_RUNTIME_ERROR",
                                    "AI Try-On encountered an inference error. Please try again."
                                )
                            else:
                                return (
                                    False,
                                    None,
                                    "SPACE_UNAVAILABLE",
                                    "AI Try-On is temporarily unavailable."
                                )

                        elif current_event in ["generating", "heartbeat"]:
                            if progress_callback:
                                progress_callback("DIFFUSION", 75, 15, self.num_timesteps, "Synthesizing garment details on ZeroGPU...")

                        elif current_event == "complete":
                            if progress_callback:
                                progress_callback("FINALIZING", 95, None, None, "Finalizing high-resolution try-on preview...")

                            # Output format: [ { "path": "...", "url": "..." }, "status_text" ]
                            if isinstance(data_json, list) and len(data_json) > 0:
                                img_info = data_json[0]
                                output_bytes = self._download_result_image(img_info)
                                if output_bytes:
                                    if output_bytes == person_image_bytes:
                                        logger.warning(f"[HF_VTO_DIAGNOSTICS] action=result_check event_id={event_id} status=IDENTICAL_REJECTED")
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

                                    logger.info(f"[HF_VTO_DIAGNOSTICS] action=success event_id={event_id} output_bytes_len={len(output_bytes)}")
                                    if progress_callback:
                                        progress_callback("COMPLETED", 100, None, None, "Virtual try-on ready!")
                                    return True, output_bytes, None, None

                            return (
                                False,
                                None,
                                "MALFORMED_RESPONSE",
                                "AI Try-On received an unexpected response from the GPU cluster."
                            )

                return (
                    False,
                    None,
                    "MALFORMED_RESPONSE",
                    "AI Try-On event stream closed before completing inference."
                )

            except requests.Timeout:
                logger.warning(f"[HF_VTO_DIAGNOSTICS] action=stream_sse event_id={event_id} status=TIMEOUT")
                return (
                    False,
                    None,
                    "INFERENCE_TIMEOUT",
                    "AI Try-On request timed out while generating your preview. Please try again."
                )
            except Exception as e:
                logger.error(f"[HF_VTO_DIAGNOSTICS] action=stream_sse event_id={event_id} err_class={type(e).__name__}")
                return (
                    False,
                    None,
                    "SPACE_UNAVAILABLE",
                    "AI Try-On is temporarily unavailable."
                )

        finally:
            with self._inflight_lock:
                self._inflight_hashes.discard(req_hash)

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
                download_urls.append(f"{self.space_url}/gradio_api/file={path}")

            headers = self._get_headers(json_content=False)

            for dl_url in download_urls:
                try:
                    resp = requests.get(dl_url, headers=headers, timeout=25)
                    if resp.status_code == 200 and len(resp.content) >= 100:
                        return resp.content
                except Exception as ex:
                    logger.warning(f"[HF_VTO_DIAGNOSTICS] action=download_result dl_url={dl_url} err_class={type(ex).__name__}")

            return None
        except Exception as e:
            logger.error(f"[HF_VTO_DIAGNOSTICS] action=download_result err_class={type(e).__name__}")
            return None

