import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

def test_health_and_readiness_probes(client: TestClient):
    """
    Test: Liveness and readiness probes report service health and database connectivity
    without leaking internal credentials or secrets.
    """
    # Liveness probe
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # Readiness probe
    res_ready = client.get("/api/v1/ready")
    assert res_ready.status_code == 200
    ready_data = res_ready.json()
    assert ready_data["status"] == "ready"
    assert ready_data["database"] == "healthy"
    assert "password" not in str(ready_data).lower()
    assert "secret" not in str(ready_data).lower()

def test_control_plane_metrics_and_firewall(client: TestClient, db: Session, setup_test_data):
    """
    Test: Control plane metric endpoints return authoritative database telemetry
    and active agent firewall invariants.
    """
    m1_id = setup_test_data["m1"]

    # 1. Firewall rules
    res_fw = client.get(f"/api/v1/agents/firewall?merchant_id={m1_id}")
    assert res_fw.status_code == 200
    fw_data = res_fw.json()
    assert fw_data["firewall_status"] == "ACTIVE"
    assert len(fw_data["global_security_invariants"]) >= 4

    # 2. Audit metrics
    res_metrics = client.get(f"/api/v1/audit/metrics?merchant_id={m1_id}")
    assert res_metrics.status_code == 200
    m_data = res_metrics.json()
    assert "agent" in m_data
    assert "commerce" in m_data
    assert "policy" in m_data
    assert "payment" in m_data
    assert "approval" in m_data
