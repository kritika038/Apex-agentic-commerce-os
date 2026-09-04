from app.auth import router as auth_router_module

class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, token_status: int = 200, userinfo_payload: dict = None):
        self.token_status = token_status
        self.userinfo_payload = userinfo_payload or {
            "sub": "google_123456",
            "email": "user@example.com",
            "name": "Example User",
            "email_verified": True,
            "picture": "https://example.com/photo.jpg"
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, data=None):
        if self.token_status != 200:
            return _FakeResponse(self.token_status, {"error": "invalid_grant"})
        return _FakeResponse(200, {"access_token": "google_access_token"})

    async def get(self, url, headers=None):
        return _FakeResponse(200, self.userinfo_payload)


def test_google_url_unconfigured_returns_clear_message(client):
    auth_router_module.settings.GOOGLE_CLIENT_ID = ""
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = ""

    response = client.get("/api/v1/auth/google/url")
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is False
    assert "Google OAuth is not configured" in data["message"]
    assert data["auth_url"] is None


def test_google_url_configured_returns_valid_oauth_url(client):
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test-client-secret"
    auth_router_module.settings.GOOGLE_REDIRECT_URI = "http://127.0.0.1:3000/auth/callback"

    response = client.get("/api/v1/auth/google/url?role=customer")
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert "accounts.google.com/o/oauth2/v2/auth" in data["auth_url"]
    assert "test-client-id.apps.googleusercontent.com" in data["auth_url"]
    assert "http%3A%2F%2F127.0.0.1%3A3000%2Fauth%2Fcallback" in data["auth_url"]


def test_google_callback_unconfigured_returns_503(client):
    auth_router_module.settings.GOOGLE_CLIENT_ID = ""
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = ""

    response = client.post(
        "/api/v1/auth/google/callback",
        json={"code": "auth_code_123"}
    )
    assert response.status_code == 503
    assert "Google OAuth is not configured" in response.json()["detail"]


def test_google_callback_ignores_frontend_role_for_new_user(monkeypatch, client, setup_test_data):
    auth_router_module.settings.GOOGLE_CLIENT_ID = "google-client-id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "google-client-secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = ""

    fake_client = _FakeAsyncClient(userinfo_payload={
        "sub": "google_cust_1",
        "email": "customer_unique_1@example.com",
        "name": "Customer User",
        "email_verified": True
    })
    monkeypatch.setattr(auth_router_module.httpx, "AsyncClient", lambda timeout=10.0: fake_client)

    response = client.post(
        "/api/v1/auth/google/callback",
        json={"code": "code_123", "role": "merchant_admin"}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "customer"
    assert response.json()["user"]["role"] == "customer"
    assert response.json()["user"]["email"] == "customer_unique_1@example.com"


def test_google_callback_merchants_allowlist_promotes_role(monkeypatch, client, setup_test_data):
    auth_router_module.settings.GOOGLE_CLIENT_ID = "google-client-id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "google-client-secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "authorized_admin@brand.com"

    fake_client = _FakeAsyncClient(userinfo_payload={
        "sub": "google_admin_1",
        "email": "authorized_admin@brand.com",
        "name": "Store Owner",
        "email_verified": True
    })
    monkeypatch.setattr(auth_router_module.httpx, "AsyncClient", lambda timeout=10.0: fake_client)

    response = client.post(
        "/api/v1/auth/google/callback",
        json={"code": "code_admin_123"}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "merchant_admin"
    assert response.json()["user"]["role"] == "merchant_admin"


def test_google_callback_unverified_email_rejected(monkeypatch, client, setup_test_data):
    auth_router_module.settings.GOOGLE_CLIENT_ID = "google-client-id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "google-client-secret"

    fake_client = _FakeAsyncClient(userinfo_payload={
        "sub": "google_unverified_1",
        "email": "unverified@example.com",
        "name": "Unverified User",
        "email_verified": False
    })
    monkeypatch.setattr(auth_router_module.httpx, "AsyncClient", lambda timeout=10.0: fake_client)

    response = client.post(
        "/api/v1/auth/google/callback",
        json={"code": "code_unverified"}
    )

    assert response.status_code == 400
    assert "not verified" in response.json()["detail"]


def test_mock_payment_simulation_blocked_when_not_mock(client, setup_test_data):
    from app.api import payments as payments_module

    original_provider = payments_module.settings.PAYMENT_PROVIDER
    original_env = payments_module.settings.ENVIRONMENT
    payments_module.settings.PAYMENT_PROVIDER = "razorpay"
    payments_module.settings.ENVIRONMENT = "development"

    try:
        response = client.post("/api/v1/payments/fake-id/simulate-mock", json={"outcome": "SUCCESS"})
        assert response.status_code == 403
    finally:
        payments_module.settings.PAYMENT_PROVIDER = original_provider
        payments_module.settings.ENVIRONMENT = original_env


def test_auth_config_allows_localhost_and_loopback_origin(client):
    response = client.get(
        "/api/v1/auth/config",
        headers={"Origin": "http://127.0.0.1:3000"}
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_merchant_is_blocked_from_customer_storefront_actions(client, db):
    login_res = client.post("/api/v1/auth/dev-login", json={"role": "merchant_admin"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    shopping_res = client.post(
        "/api/v1/ai/shopping",
        json={"session_id": "sess_block_merchant", "message": "show me shoes"},
        headers=headers
    )
    assert shopping_res.status_code == 403

    intent_res = client.post(
        "/api/v1/purchase-intents/",
        json={"session_id": "sess_block_merchant", "buyer_id": "merchant-user"},
        headers=headers
    )
    assert intent_res.status_code == 403


def test_customer_is_blocked_from_merchant_purchase_intent_dashboard(client, db):
    login_res = client.post("/api/v1/auth/dev-login", json={"role": "customer"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/purchase-intents/", headers=headers)
    assert response.status_code == 403
