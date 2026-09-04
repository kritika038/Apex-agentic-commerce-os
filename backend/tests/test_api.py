def test_login_success(client, setup_test_data):
    res = client.post("/api/v1/auth/login", data={"username": "u1@m1.com", "password": "testpass"})
    assert res.status_code == 200
    assert "access_token" in res.json()

def test_login_failure(client, setup_test_data):
    res = client.post("/api/v1/auth/login", data={"username": "u1@m1.com", "password": "wrong"})
    assert res.status_code == 401

def test_create_product(client, auth_headers):
    headers = auth_headers("u1@m1.com")
    res = client.post("/api/v1/products/", json={
        "name": "Test Product",
        "category": "Test",
        "price": 100.0,
        "stock_quantity": 50
    }, headers=headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Test Product"
    assert "id" in res.json()

def test_product_merchant_isolation(client, auth_headers, setup_test_data):
    # u1 creates a product
    headers1 = auth_headers("u1@m1.com")
    res1 = client.post("/api/v1/products/", json={
        "name": "M1 Product",
        "category": "Test",
        "price": 100.0
    }, headers=headers1)
    p_id = res1.json()["id"]

    # u2 (merchant 2) tries to read it
    headers2 = auth_headers("u2@m2.com")
    res2 = client.get(f"/api/v1/products/{p_id}", headers=headers2)
    assert res2.status_code == 404 # Isolated!

    # u2 tries to list products, should not see M1 Product
    res3 = client.get("/api/v1/products/", headers=headers2)
    assert len(res3.json()) == 0

    # u1 should see it
    res4 = client.get("/api/v1/products/", headers=headers1)
    assert len(res4.json()) == 1

def test_unauthorized_merchant_access(client, auth_headers, setup_test_data):
    # User with no merchant tries to create product
    headers3 = auth_headers("u3@none.com")
    res = client.post("/api/v1/products/", json={
        "name": "No Merchant Product",
        "category": "Test",
        "price": 100.0
    }, headers=headers3)
    assert res.status_code == 403
