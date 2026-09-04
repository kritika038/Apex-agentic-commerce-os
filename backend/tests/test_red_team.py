import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.models.merchant import Merchant

client = TestClient(app)

def test_ai_red_team_security_lab_scenarios_and_execution(client, db):
    merchant = Merchant(name="Defense Test Merchant", domain="defense.test", is_active=True)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)

    # 1. Fetch 12 Attack Scenarios
    res_scenarios = client.get("/api/v1/security-lab/scenarios")
    assert res_scenarios.status_code == 200
    scenarios = res_scenarios.json()
    assert len(scenarios) == 12

    expected_ids = [
        "ATTACK_01_PRICE_MANIPULATION",
        "ATTACK_02_EXCESSIVE_QUANTITY",
        "ATTACK_03_CURRENCY_MANIPULATION",
        "ATTACK_04_POLICY_BYPASS",
        "ATTACK_05_PERMISSION_ESCALATION",
        "ATTACK_06_CROSS_MERCHANT_ACCESS",
        "ATTACK_07_PAYMENT_REPLAY",
        "ATTACK_08_FORGED_WEBHOOK",
        "ATTACK_09_AUDIT_TAMPERING",
        "ATTACK_10_UNKNOWN_BLIND_RETRY",
        "ATTACK_11_EXPIRED_AUTHORIZATION",
        "ATTACK_12_PROMPT_INJECTION"
    ]
    returned_ids = [s["scenario_id"] for s in scenarios]
    assert returned_ids == expected_ids

    # 2. Run all 12 Attacks
    res_all = client.post(f"/api/v1/security-lab/run-all?merchant_id={merchant.id}")
    assert res_all.status_code == 200
    data = res_all.json()
    assert data["system_security_score"] == 100.0
    assert data["total_attacks"] == 12
    assert data["blocked_attacks"] == 11
    assert data["idempotent_attacks"] == 1
    assert data["security_failures"] == 0
    assert data["status_label"] == "INTERNAL_SECURITY_VERIFICATION_PASS"

    for r in data["results"]:
        assert r["blocked"] is True
        assert "✓" in r["actual_result"]

    # 3. Run individual attack
    res_single = client.post(f"/api/v1/security-lab/run/ATTACK_01_PRICE_MANIPULATION?merchant_id={merchant.id}")
    assert res_single.status_code == 200
    assert res_single.json()["scenario_id"] == "ATTACK_01_PRICE_MANIPULATION"
    assert res_single.json()["blocked"] is True

    # 4. Fetch results history
    res_history = client.get(f"/api/v1/security-lab/results?merchant_id={merchant.id}")
    assert res_history.status_code == 200
    assert len(res_history.json()) >= 12
