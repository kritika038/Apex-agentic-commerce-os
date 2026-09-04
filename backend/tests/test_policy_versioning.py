import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.policy import Policy
from app.database.models.policy_evaluation import PolicyEvaluation
from app.services.purchase_intent_service import PurchaseIntentService
from app.policies.policy_engine import PolicyEngine
from app.tools.shopping_tools import add_to_cart

def test_historical_policy_evaluation_reproducibility(client: TestClient, db: Session, setup_test_data, auth_headers):
    """
    Test that updating merchant policy from v1 to v2 creates an immutable new version
    and preserves historical PolicyEvaluation snapshots permanently.
    """
    m1_id = setup_test_data["m1"]
    headers = auth_headers("u1@m1.com")

    # 1. Create Policy v1: Approval Threshold = ₹5,000
    policy_v1 = Policy(
        merchant_id=m1_id,
        name="Commerce Policy v1",
        version=1,
        max_transaction_amount=Decimal("10000.00"),
        approval_threshold=Decimal("5000.00"),
        low_risk_limit=Decimal("2000.00"),
        max_quantity=5,
        allowed_currency="INR",
        is_active=True
    )
    db.add(policy_v1)

    p_shoes = Product(merchant_id=m1_id, name="Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    p_socks = Product(merchant_id=m1_id, name="Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
    db.add_all([p_shoes, p_socks])
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_shoes.id, stock_quantity=20))
    db.add(Inventory(merchant_id=m1_id, product_id=p_socks.id, stock_quantity=50))
    db.commit()

    # 2. Evaluate Purchase Intent under v1 (₹3,898 <= ₹5,000 -> ALLOW)
    session_1 = "sess_v1_eval"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_1, product_id=p_shoes.id, quantity=1)
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_1, product_id=p_socks.id, quantity=1)

    intent_1 = PurchaseIntentService.create_purchase_intent(db=db, merchant_id=m1_id, session_id=session_1, buyer_id="buyer_v1")
    eval_1 = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent_1.id, merchant_id=m1_id)
    
    assert eval_1["decision"] == "ALLOW"
    assert eval_1["policy_version"] == 1
    assert eval_1["policy_snapshot"]["approval_threshold"] == "5000.00"

    # 3. Update Policy via API to v2: Tighten Approval Threshold to ₹3,000
    res_update = client.put(f"/api/v1/policies/{policy_v1.id}", json={
        "approval_threshold": 3000.0
    }, headers=headers)
    assert res_update.status_code == 200
    new_policy_data = res_update.json()
    assert new_policy_data["version"] == 2
    assert Decimal(str(new_policy_data["approval_threshold"])) == Decimal("3000.00")

    # 4. Verify old evaluation record in DB remains completely unchanged (v1 snapshot)
    eval_old = db.query(PolicyEvaluation).filter(PolicyEvaluation.id == eval_1["id"]).first()
    assert eval_old.policy_version == 1
    assert eval_old.policy_snapshot["approval_threshold"] == "5000.00"
    assert eval_old.decision == "ALLOW"

    # 5. Evaluate a new Purchase Intent with same amount under v2 (₹3,898 > ₹3,000 -> REQUIRES_APPROVAL)
    session_2 = "sess_v2_eval"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_2, product_id=p_shoes.id, quantity=1)
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_2, product_id=p_socks.id, quantity=1)

    intent_2 = PurchaseIntentService.create_purchase_intent(db=db, merchant_id=m1_id, session_id=session_2, buyer_id="buyer_v2")
    eval_2 = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent_2.id, merchant_id=m1_id)

    assert eval_2["decision"] == "REQUIRES_APPROVAL"
    assert eval_2["policy_version"] == 2
    assert eval_2["policy_snapshot"]["approval_threshold"] == "3000.00"
