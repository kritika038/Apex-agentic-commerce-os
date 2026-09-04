import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.virtual_tryon.providers.huggingface_zerogpu import HuggingFaceZeroGPUProvider
from app.services.virtual_tryon.providers.local_fashn import LocalFashnVTONProvider
from app.services.virtual_tryon.registry import VTOProviderRegistry
from app.services.virtual_tryon.service import VirtualTryOnService
from app.database.models.product import Product

SAMPLE_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 200
SAMPLE_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 200
SYNTHESIZED_RESULT = b"\xff\xd8\xff\xe0\x00\x10JFIF_SYNTHESIZED_VTO_IMAGE_BYTES" + b"\x11" * 300

client = TestClient(app)

def test_registry_selects_huggingface_zerogpu():
    VTOProviderRegistry.clear_cache()
    provider = VTOProviderRegistry.get_provider("huggingface_zerogpu")
    assert isinstance(provider, HuggingFaceZeroGPUProvider)
    assert provider.provider_id == "huggingface_zerogpu"
    assert provider.is_demo is False
    assert provider.is_available is True

def test_registry_handles_quotes_and_aliases(monkeypatch):
    for alias in ['"huggingface_zerogpu"', "'huggingface_zerogpu'", "hf_zerogpu", "zerogpu", "huggingface-zerogpu", "hf-zerogpu"]:
        monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", alias)
        VTOProviderRegistry.clear_cache()
        provider = VTOProviderRegistry.get_provider()
        assert isinstance(provider, HuggingFaceZeroGPUProvider), f"Failed for alias: {alias}"

def test_registry_preserves_local_fashn():
    VTOProviderRegistry.clear_cache()
    provider = VTOProviderRegistry.get_provider("local_fashn")
    assert isinstance(provider, LocalFashnVTONProvider)
    assert provider.provider_id == "local_fashn"

def test_vto_health_endpoint_ready(monkeypatch):
    monkeypatch.setenv("VIRTUAL_TRYON_ENABLED", "true")
    monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", "huggingface_zerogpu")
    monkeypatch.setenv("VTO_HF_SPACE_URL", "https://kritika68-apex-vton.hf.space")
    VTOProviderRegistry.clear_cache()

    response = client.get("/api/v1/virtual-tryon/health")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "huggingface_zerogpu"
    assert data["enabled"] is True
    assert data["state"] == "READY"
    assert data["message"] == "AI Try-On"
    assert "token" not in str(data).lower()
    assert "disabled by administrator" not in str(data).lower()

def test_vto_health_endpoint_disabled(monkeypatch):
    monkeypatch.setenv("VIRTUAL_TRYON_ENABLED", "false")
    VTOProviderRegistry.clear_cache()

    response = client.get("/api/v1/virtual-tryon/health")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["state"] == "CONFIGURATION_ERROR"

def test_category_mapping():
    provider = HuggingFaceZeroGPUProvider()
    assert provider._map_category("CLOTHING", {"name": "Summer Floral Dress", "category": "Dresses"}) == "one-pieces"
    assert provider._map_category("CLOTHING", {"name": "Slim Fit Cargo Pants", "category": "Bottoms"}) == "bottoms"
    assert provider._map_category("CLOTHING", {"name": "Performance Running Tee", "category": "Apparel"}) == "tops"
    assert provider._map_category("CLOTHING", {"name": "Ankle Length Leggings", "subcategory": "track pants"}) == "bottoms"

def test_shoes_and_unsupported_rejected_by_service():
    shoe = Product(
        name="Nike Air Zoom Pegasus 40",
        category="Footwear",
        subcategory="Running Shoes",
        image_url="https://images.unsplash.com/shoe.jpg"
    )
    elig = VirtualTryOnService.is_virtual_tryon_supported(shoe)
    assert elig.supported is False
    assert "apparel only" in elig.reason.lower() or "footwear" in elig.reason.lower()

    bottle = Product(
        name="Stainless Steel Gym Shaker Bottle",
        category="Accessories",
        subcategory="Bottles",
        image_url="https://images.unsplash.com/bottle.jpg"
    )
    elig2 = VirtualTryOnService.is_virtual_tryon_supported(bottle)
    assert elig2.supported is False
    assert "does not support" in elig2.reason.lower()

def test_invalid_inputs_rejected():
    provider = HuggingFaceZeroGPUProvider()
    ok, res, code, msg = provider.generate_try_on(
        person_image_bytes=b"short",
        product_image_url="https://images.unsplash.com/garment.jpg",
        garment_type="CLOTHING",
        product_metadata={"name": "Nike Tee", "category": "Apparel"}
    )
    assert ok is False
    assert code == "INVALID_PERSON_IMAGE"

    ok2, res2, code2, msg2 = provider.generate_try_on(
        person_image_bytes=SAMPLE_JPEG,
        product_image_url="",
        garment_type="CLOTHING",
        product_metadata={"name": "Nike Tee", "category": "Apparel"}
    )
    assert ok2 is False
    assert code2 == "INVALID_GARMENT_IMAGE"

def test_hf_successful_inference_simulation():
    provider = HuggingFaceZeroGPUProvider(space_url="https://test-space.hf.space")

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        garment_resp = MagicMock(status_code=200, content=SAMPLE_PNG)
        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = ["/tmp/gradio/uploaded_file.jpg"]
        call_resp = MagicMock(status_code=200)
        call_resp.json.return_value = {"event_id": "test_event_123"}

        mock_post.side_effect = [upload_resp, upload_resp, call_resp]

        sse_lines = [
            b"event: generating\n",
            b"data: [null, \"Processing diffusion steps\"]\n\n",
            b"event: complete\n",
            b"data: [{\"path\": \"/tmp/gradio/out.png\", \"url\": \"https://test-space.hf.space/file.png\"}, \"Try-on ready\"]\n\n"
        ]
        stream_resp = MagicMock(status_code=200)
        stream_resp.iter_lines.return_value = sse_lines

        final_img_resp = MagicMock(status_code=200, content=SYNTHESIZED_RESULT)
        mock_get.side_effect = [garment_resp, stream_resp, final_img_resp]

        progress_events = []
        def on_prog(stage, pct, step, total, msg):
            progress_events.append((stage, pct, msg))

        ok, result_bytes, err_code, err_msg = provider.generate_try_on(
            person_image_bytes=SAMPLE_JPEG,
            product_image_url="https://images.unsplash.com/garment.jpg",
            garment_type="CLOTHING",
            product_metadata={"name": "Nike Dri-FIT Tee", "category": "Apparel"},
            progress_callback=on_prog
        )

        assert ok is True
        assert result_bytes == SYNTHESIZED_RESULT
        assert err_code is None
        assert err_msg is None
        assert any(e[0] == "PREPARING" for e in progress_events)
        assert any(e[0] == "DIFFUSION" for e in progress_events)
        assert any(e[0] == "COMPLETED" for e in progress_events)

def test_zerogpu_quota_exhausted_handling():
    provider = HuggingFaceZeroGPUProvider(space_url="https://test-space.hf.space")

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        garment_resp = MagicMock(status_code=200, content=SAMPLE_PNG)
        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = ["/tmp/gradio/uploaded_file.jpg"]
        call_resp = MagicMock(status_code=200)
        call_resp.json.return_value = {"event_id": "test_event_quota"}

        mock_post.side_effect = [upload_resp, upload_resp, call_resp]

        sse_lines = [
            b"event: error\n",
            b"data: {\"error\": \"You have exceeded your ZeroGPU quota (180s requested vs. 148s left). Try again in 23:24:36.\"}\n\n"
        ]
        stream_resp = MagicMock(status_code=200)
        stream_resp.iter_lines.return_value = sse_lines
        mock_get.side_effect = [garment_resp, stream_resp]

        ok, result_bytes, err_code, err_msg = provider.generate_try_on(
            person_image_bytes=SAMPLE_JPEG,
            product_image_url="https://images.unsplash.com/garment.jpg",
            garment_type="CLOTHING",
            product_metadata={"name": "Nike Tee", "category": "Apparel"}
        )

        assert ok is False
        assert err_code == "ZEROGPU_QUOTA_EXHAUSTED"
        assert "reached today's free gpu limit" in err_msg.lower()

def test_zerogpu_busy_handling():
    provider = HuggingFaceZeroGPUProvider(space_url="https://test-space.hf.space")

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        garment_resp = MagicMock(status_code=200, content=SAMPLE_PNG)
        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = ["/tmp/gradio/uploaded_file.jpg"]
        call_resp = MagicMock(status_code=200)
        call_resp.json.return_value = {"event_id": "test_event_busy"}

        mock_post.side_effect = [upload_resp, upload_resp, call_resp]

        sse_lines = [
            b"event: error\n",
            b"data: {\"error\": \"All GPUs are currently busy in queue. Please wait.\"}\n\n"
        ]
        stream_resp = MagicMock(status_code=200)
        stream_resp.iter_lines.return_value = sse_lines
        mock_get.side_effect = [garment_resp, stream_resp]

        ok, result_bytes, err_code, err_msg = provider.generate_try_on(
            person_image_bytes=SAMPLE_JPEG,
            product_image_url="https://images.unsplash.com/garment.jpg",
            garment_type="CLOTHING",
            product_metadata={"name": "Nike Tee", "category": "Apparel"}
        )

        assert ok is False
        assert err_code == "ZEROGPU_BUSY"
        assert "temporarily busy" in err_msg.lower()

def test_space_sleeping_or_503_handling():
    provider = HuggingFaceZeroGPUProvider(space_url="https://test-space.hf.space")

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        garment_resp = MagicMock(status_code=200, content=SAMPLE_PNG)
        mock_get.return_value = garment_resp
        mock_post.return_value = MagicMock(status_code=503)

        ok, result_bytes, err_code, err_msg = provider.generate_try_on(
            person_image_bytes=SAMPLE_JPEG,
            product_image_url="https://images.unsplash.com/garment.jpg",
            garment_type="CLOTHING",
            product_metadata={"name": "Nike Tee", "category": "Apparel"}
        )

        assert ok is False
        assert err_code == "SPACE_SLEEPING_OR_RESTARTING"
        assert "temporarily unavailable" in err_msg.lower()

def test_identical_output_rejected():
    provider = HuggingFaceZeroGPUProvider(space_url="https://test-space.hf.space")

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        garment_resp = MagicMock(status_code=200, content=SAMPLE_PNG)
        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = ["/tmp/gradio/uploaded_file.jpg"]
        call_resp = MagicMock(status_code=200)
        call_resp.json.return_value = {"event_id": "test_event_identical"}

        mock_post.side_effect = [upload_resp, upload_resp, call_resp]

        sse_lines = [
            b"event: complete\n",
            b"data: [{\"path\": \"/tmp/gradio/out.jpg\", \"url\": \"https://test-space.hf.space/out.jpg\"}]\n\n"
        ]
        stream_resp = MagicMock(status_code=200)
        stream_resp.iter_lines.return_value = sse_lines

        # Return identical input image bytes
        final_img_resp = MagicMock(status_code=200, content=SAMPLE_JPEG)
        mock_get.side_effect = [garment_resp, stream_resp, final_img_resp]

        ok, result_bytes, err_code, err_msg = provider.generate_try_on(
            person_image_bytes=SAMPLE_JPEG,
            product_image_url="https://images.unsplash.com/garment.jpg",
            garment_type="CLOTHING",
            product_metadata={"name": "Nike Tee", "category": "Apparel"}
        )

        assert ok is False
        assert err_code == "IDENTICAL_OUTPUT_REJECTED"
        assert "unmodified" in err_msg.lower()
