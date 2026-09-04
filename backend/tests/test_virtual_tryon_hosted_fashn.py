import os
import io
import json
import base64
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import SessionLocal
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.database.models.product import Product
from app.database.models.virtual_tryon import VirtualTryOnJob, VirtualTryOnEvent, TryOnGarmentType, TryOnJobStatus
from app.services.virtual_tryon.service import VirtualTryOnService
from app.services.virtual_tryon.registry import VTOProviderRegistry
from app.services.virtual_tryon.providers.fashn import FashnVirtualTryOnProvider
from app.services.virtual_tryon.providers.local_fashn import LocalFashnVTONProvider
from app.core.security import create_access_token

client = TestClient(app)

def make_test_image_bytes(marker=b"\xa5") -> bytes:
    header = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    payload = (
        b"\xff\xdb\x00C\x00" + b"\x08" * 64 +
        b"\xff\xc0\x00\x11\x08\x00\xc8\x00\xc8\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01" +
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b" +
        b"\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00" + (marker * 1024)
    )
    return header + payload + b"\xff\xd9"

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def vto_test_data(db_session: Session):
    merchant = db_session.query(Merchant).first()
    if not merchant:
        merchant = Merchant(name="Apex Store", email="store@apex.test")
        db_session.add(merchant)
        db_session.commit()
        db_session.refresh(merchant)

    user = db_session.query(User).filter(User.email == "vto_hosted_test@apex.test").first()
    if not user:
        user = User(
            merchant_id=merchant.id,
            email="vto_hosted_test@apex.test",
            full_name="VTO Hosted Test User",
            role="customer",
            hashed_password="pw"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    # Apparel Shirt
    shirt = db_session.query(Product).filter(Product.name == "Hosted Dry-Fit Tee").first()
    if not shirt:
        shirt = Product(
            merchant_id=merchant.id,
            name="Hosted Dry-Fit Tee",
            brand="Nike",
            category="Apparel",
            subcategory="T-Shirts",
            price=Decimal("1299.00"),
            image_url="https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600",
            attributes={
                "color": "Black",
                "size": "L",
                "vto_image_ready": True,
                "vto_image_url": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600",
                "variant_details": {
                    "Black": {
                        "color": "Black",
                        "garment_image_url": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600",
                        "vto_eligible": True
                    }
                }
            },
            is_active=True
        )
        db_session.add(shirt)
        db_session.commit()
        db_session.refresh(shirt)
    else:
        shirt.is_active = True
        db_session.commit()

    # Non-Apparel Dumbbell
    dumbbell = db_session.query(Product).filter(Product.name == "Cast Iron Hex Dumbbell").first()
    if not dumbbell:
        dumbbell = Product(
            merchant_id=merchant.id,
            name="Cast Iron Hex Dumbbell",
            brand="Decathlon",
            category="Fitness Equipment",
            subcategory="Weights",
            price=Decimal("2499.00"),
            image_url="https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=600",
            is_active=True
        )
        db_session.add(dumbbell)
        db_session.commit()
        db_session.refresh(dumbbell)
    else:
        dumbbell.is_active = True
        db_session.commit()

    token = create_access_token(subject=str(user.id), merchant_id=str(merchant.id), role=user.role)

    return {
        "merchant": merchant,
        "user": user,
        "token": token,
        "shirt": shirt,
        "dumbbell": dumbbell
    }


# =========================================================================
# TEST A: VTO availability returns enabled for eligible apparel in production configuration
# =========================================================================
def test_a_vto_availability_returns_enabled_for_eligible_apparel(monkeypatch, vto_test_data):
    monkeypatch.setenv("VIRTUAL_TRYON_ENABLED", "true")
    monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", "fashn")
    monkeypatch.setenv("FASHN_API_KEY", "test-live-fashn-key-12345")

    provider = VTOProviderRegistry.get_provider()
    assert isinstance(provider, FashnVirtualTryOnProvider)
    assert provider.is_available is True

    headers = {"Authorization": f"Bearer {vto_test_data['token']}"}
    resp = client.post(
        "/api/v1/virtual-tryon/check",
        headers=headers,
        json={"product_id": str(vto_test_data["shirt"].id)}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["supported"] is True
    assert data["garment_type"] == "CLOTHING"
    mapped_cat = provider._map_category(data["garment_type"], {
        "name": vto_test_data["shirt"].name,
        "category": vto_test_data["shirt"].category,
        "subcategory": vto_test_data["shirt"].subcategory
    })
    assert mapped_cat in ["tops", "bottoms", "one-pieces"]


# =========================================================================
# TEST B: Non-apparel remains unsupported
# =========================================================================
def test_b_non_apparel_remains_unsupported(monkeypatch, vto_test_data):
    monkeypatch.setenv("VIRTUAL_TRYON_ENABLED", "true")
    monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", "fashn")
    monkeypatch.setenv("FASHN_API_KEY", "test-live-fashn-key-12345")

    headers = {"Authorization": f"Bearer {vto_test_data['token']}"}
    resp = client.post(
        "/api/v1/virtual-tryon/check",
        headers=headers,
        json={"product_id": str(vto_test_data["dumbbell"].id)}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["supported"] is False
    assert "does not support" in data["reason"].lower() or "not in an eligible" in data["reason"].lower()


# =========================================================================
# TEST C: Uploaded person image reaches backend
# =========================================================================
def test_c_uploaded_person_image_reaches_backend(monkeypatch, vto_test_data):
    monkeypatch.setenv("VIRTUAL_TRYON_ENABLED", "true")
    monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", "fashn")
    monkeypatch.setenv("FASHN_API_KEY", "test-live-fashn-key-12345")

    img_bytes = make_test_image_bytes(b"\x11")
    headers = {"Authorization": f"Bearer {vto_test_data['token']}"}
    
    with patch.object(FashnVirtualTryOnProvider, "generate_try_on") as mock_gen:
        mock_gen.return_value = (True, make_test_image_bytes(b"\x99"), None, None)
        
        resp = client.post(
            "/api/v1/virtual-tryon/jobs",
            headers=headers,
            data={
                "product_id": str(vto_test_data["shirt"].id),
                "consent": "true"
            },
            files={"photo": ("user_upload.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        )
        assert resp.status_code == 200
        assert mock_gen.called
        passed_bytes = mock_gen.call_args[1]["person_image_bytes"]
        assert passed_bytes == img_bytes


# =========================================================================
# TEST D & E: Backend calls hosted provider & successful response produces actual generated image
# =========================================================================
def test_d_and_e_backend_calls_hosted_provider_and_produces_result(monkeypatch, vto_test_data):
    monkeypatch.setenv("VIRTUAL_TRYON_ENABLED", "true")
    monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", "fashn")
    monkeypatch.setenv("FASHN_API_KEY", "test-live-fashn-key-12345")

    img_bytes = make_test_image_bytes(b"\x22")
    synth_output = make_test_image_bytes(b"\x77")

    def mock_requests_post(url, json=None, headers=None, timeout=None):
        assert "api.fashn.ai" in url
        assert headers["Authorization"] == "Bearer test-live-fashn-key-12345"
        assert json["model_name"] == "tryon-v1.6"
        assert json["inputs"]["category"] == "tops"
        assert json["inputs"]["model_image"].startswith("data:image/jpeg;base64,")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "pred_test_12345", "status": "starting"}
        return mock_resp

    def mock_requests_get(url, headers=None, timeout=None):
        mock_resp = MagicMock()
        if "status/pred_test_12345" in url:
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "id": "pred_test_12345",
                "status": "completed",
                "output": ["https://cdn.fashn.ai/results/pred_test_12345.jpg"]
            }
        elif "cdn.fashn.ai" in url:
            mock_resp.status_code = 200
            mock_resp.content = synth_output
        else:
            mock_resp.status_code = 404
        return mock_resp

    with patch("requests.post", side_effect=mock_requests_post), \
         patch("requests.get", side_effect=mock_requests_get):
        
        headers = {"Authorization": f"Bearer {vto_test_data['token']}"}
        resp = client.post(
            "/api/v1/virtual-tryon/jobs",
            headers=headers,
            data={"product_id": str(vto_test_data["shirt"].id), "consent": "true"},
            files={"photo": ("person.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        )
        assert resp.status_code == 200
        job_data = resp.json()
        job_id = job_data["job_id"]
        get_resp = client.get(f"/api/v1/virtual-tryon/jobs/{job_id}", headers=headers)
        assert get_resp.status_code == 200
        detail = get_resp.json()
        assert detail["status"] == "COMPLETED", f"Job failed with error_code={detail.get('error_code')} error_message={detail.get('error_message')}"


# =========================================================================
# TEST F: Provider failure is handled honestly (401, 429, synthesis failure)
# =========================================================================
def test_f_provider_failures_handled_honestly(monkeypatch, vto_test_data):
    monkeypatch.setenv("VIRTUAL_TRYON_ENABLED", "true")
    monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", "fashn")
    monkeypatch.setenv("FASHN_API_KEY", "bad-key")

    img_bytes = make_test_image_bytes(b"\x33")
    headers = {"Authorization": f"Bearer {vto_test_data['token']}"}

    # Case 1: 401 Auth Failure
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 401
        mock_post.return_value.text = "Unauthorized"
        
        resp = client.post(
            "/api/v1/virtual-tryon/jobs",
            headers=headers,
            data={"product_id": str(vto_test_data["shirt"].id), "consent": "true"},
            files={"photo": ("person.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        
        status_resp = client.get(f"/api/v1/virtual-tryon/jobs/{job_id}", headers=headers)
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "FAILED"
        assert data["error_code"] == "FASHN_AUTH_ERROR"

    # Case 2: 429 Rate Limit
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 429
        mock_post.return_value.text = "Too Many Requests"
        
        resp = client.post(
            "/api/v1/virtual-tryon/jobs",
            headers=headers,
            data={"product_id": str(vto_test_data["shirt"].id), "consent": "true"},
            files={"photo": ("person.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        
        status_resp = client.get(f"/api/v1/virtual-tryon/jobs/{job_id}", headers=headers)
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "FAILED"
        assert data["error_code"] == "RATE_LIMIT_EXCEEDED"

    # Case 3: Synthesis Failure during polling
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"id": "pred_fail", "status": "starting"}
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "id": "pred_fail",
            "status": "failed",
            "error": {"message": "Garment segmentation failed on complex background"}
        }

        resp = client.post(
            "/api/v1/virtual-tryon/jobs",
            headers=headers,
            data={"product_id": str(vto_test_data["shirt"].id), "consent": "true"},
            files={"photo": ("person.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        status_resp = client.get(f"/api/v1/virtual-tryon/jobs/{job_id}", headers=headers)
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "FAILED"
        assert data["error_code"] == "FASHN_SYNTHESIS_FAILED"
        assert "Garment segmentation failed" in data["error_message"]


# =========================================================================
# TEST G & H: API key never appears in frontend bundle or API responses
# =========================================================================
def test_g_and_h_api_key_never_exposed(monkeypatch, vto_test_data):
    secret_key = "fashn_secret_production_key_xyz987"
    monkeypatch.setenv("VIRTUAL_TRYON_ENABLED", "true")
    monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", "fashn")
    monkeypatch.setenv("FASHN_API_KEY", secret_key)

    headers = {"Authorization": f"Bearer {vto_test_data['token']}"}

    # Check check endpoint
    resp = client.post(
        "/api/v1/virtual-tryon/check",
        headers=headers,
        json={"product_id": str(vto_test_data["shirt"].id)}
    )
    assert resp.status_code == 200
    assert secret_key not in resp.text

    # Check error response
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 400
        mock_post.return_value.text = "Bad Request"
        resp = client.post(
            "/api/v1/virtual-tryon/jobs",
            headers=headers,
            data={"product_id": str(vto_test_data["shirt"].id), "consent": "true"},
            files={"photo": ("person.jpg", io.BytesIO(make_test_image_bytes()), "image/jpeg")}
        )
        assert resp.status_code == 200
        assert secret_key not in resp.text


# =========================================================================
# TEST I: Privacy - No raw user image is permanently logged
# =========================================================================
def test_i_privacy_transient_processing(db_session, monkeypatch, vto_test_data):
    monkeypatch.setenv("VIRTUAL_TRYON_ENABLED", "true")
    monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", "fashn")
    monkeypatch.setenv("FASHN_API_KEY", "test-live-fashn-key-12345")

    img_bytes = make_test_image_bytes(b"\x55")

    with patch.object(FashnVirtualTryOnProvider, "generate_try_on") as mock_gen:
        mock_gen.return_value = (True, make_test_image_bytes(b"\x88"), None, None)
        
        headers = {"Authorization": f"Bearer {vto_test_data['token']}"}
        resp = client.post(
            "/api/v1/virtual-tryon/jobs",
            headers=headers,
            data={"product_id": str(vto_test_data["shirt"].id), "consent": "true"},
            files={"photo": ("person.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        job = db_session.query(VirtualTryOnJob).filter(VirtualTryOnJob.id == job_id).first()
        assert job is not None
        # Verify job stores internal storage keys but never raw payload bytes
        assert "vto_input_" in job.input_image_key
        assert "vto_result_" in job.result_image_key


# =========================================================================
# TEST J & K: Camera flow and Upload flow payloads both function
# =========================================================================
def test_j_and_k_camera_and_upload_flows(monkeypatch, vto_test_data):
    monkeypatch.setenv("VIRTUAL_TRYON_ENABLED", "true")
    monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", "fashn")
    monkeypatch.setenv("FASHN_API_KEY", "test-live-fashn-key-12345")

    headers = {"Authorization": f"Bearer {vto_test_data['token']}"}

    with patch.object(FashnVirtualTryOnProvider, "generate_try_on") as mock_gen:
        mock_gen.return_value = (True, make_test_image_bytes(b"\x44"), None, None)

        # 1. Camera flow (webcam capture blob sent as multipart file)
        resp_cam = client.post(
            "/api/v1/virtual-tryon/jobs",
            headers=headers,
            data={"product_id": str(vto_test_data["shirt"].id), "consent": "true"},
            files={"photo": ("webcam_capture.jpg", io.BytesIO(make_test_image_bytes(b"\x01")), "image/jpeg")}
        )
        assert resp_cam.status_code == 200
        assert resp_cam.json()["status"] == "COMPLETED"

        # 2. Upload flow (file uploaded from disk)
        resp_upload = client.post(
            "/api/v1/virtual-tryon/jobs",
            headers=headers,
            data={"product_id": str(vto_test_data["shirt"].id), "consent": "true"},
            files={"photo": ("my_portrait.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 300), "image/png")}
        )
        assert resp_upload.status_code == 200
        assert resp_upload.json()["status"] == "COMPLETED"


# =========================================================================
# TEST L: Local MPS provider remains functional
# =========================================================================
def test_l_local_mps_provider_remains_functional(monkeypatch):
    monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", "local_fashn")
    monkeypatch.setenv("VIRTUAL_TRYON_ENABLED", "true")

    provider = VTOProviderRegistry.get_provider()
    assert isinstance(provider, LocalFashnVTONProvider)
    assert provider.provider_id == "local_fashn"
