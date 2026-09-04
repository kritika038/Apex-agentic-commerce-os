import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.merchant import Merchant
from app.database.models.cart import Cart, CartItem
from app.agents.sales_agent import SalesAgent
from app.tools.registry import tool_registry
from app.tools.shopping_tools import add_to_cart

def test_sales_agent_permission_boundaries():
    """
    Verify that Sales Agent does not possess payment, price modification, or policy override permissions.
    """
    agent = SalesAgent(db=None, merchant_id="m_test", session_id="s_test")
    forbidden_permissions = [
        "CREATE_PAYMENT_ORDER",
        "EXECUTE_PAYMENT",
        "MODIFY_PRICE",
        "OVERRIDE_POLICY",
        "PROCESS_REFUND"
    ]
    for perm in forbidden_permissions:
        assert perm not in agent.permissions

def test_no_payment_endpoints_exist_in_phase_3(client: TestClient):
    """
    Verify strict Phase 3 boundary: No direct payment execution or arbitrary Razorpay endpoints are exposed.
    """
    res_pay = client.post("/api/v1/payments/create", json={})
    assert res_pay.status_code in (404, 405)

    res_razor = client.post("/api/v1/razorpay/order", json={})
    assert res_razor.status_code in (404, 405)

def test_tenant_isolation_for_purchase_intents(client: TestClient, db: Session, setup_test_data):
    """
    Verify Purchase Intents created under Merchant 1 are not accessible by Merchant 2.
    """
    m1_id = setup_test_data["m1"]
    m2_id = setup_test_data["m2"]
    session_id = "sess_iso_pi"

    # Setup Product for M1
    p1 = Product(merchant_id=m1_id, name="Pro Running Shoes", price=3499.0, category="Running", is_active=True)
    db.add(p1)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=10))
    db.commit()

    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)

    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_iso",
        "merchant_id": m1_id
    })
    intent_id = res_pi.json()["id"]

    # M2 queries the intent
    res_get_m2 = client.get(f"/api/v1/purchase-intents/{intent_id}?merchant_id={m2_id}")
    assert res_get_m2.status_code == 404

    # M2 lists purchase intents
    res_list_m2 = client.get(f"/api/v1/purchase-intents/?merchant_id={m2_id}")
    assert res_list_m2.status_code == 200
    m2_intents = res_list_m2.json()
    assert len(m2_intents) == 0
