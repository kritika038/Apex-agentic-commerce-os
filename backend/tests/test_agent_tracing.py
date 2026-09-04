import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.database.models.agent_trace import AgentTrace
from app.database.models.agent_step import AgentStep
from app.services.agent_tracing_service import AgentTracingService
from app.agents.shopping_agent import ShoppingAgent

def test_agent_trace_and_step_lifecycle(db: Session, setup_test_data):
    """
    Test: AgentTrace and AgentStep records store structured hashes, latency, and step sequence.
    """
    m1_id = setup_test_data["m1"]
    trace_id = "trc_agent_life_001"

    # Start trace
    at = AgentTracingService.start_agent_trace(
        db=db,
        trace_id=trace_id,
        merchant_id=m1_id,
        agent_id="ShoppingAgent",
        agent_type="SHOPPING_AGENT",
        agent_version="1.0.0",
        input_data={"message": "find running shoes"}
    )
    db.commit()

    assert at.id is not None
    assert at.input_hash is not None
    assert at.status == "STARTED"

    # Record steps
    s1 = AgentTracingService.record_step(
        db=db,
        trace_id=trace_id,
        agent_trace_id=at.id,
        sequence_number=1,
        step_type="TOOL_CALL",
        tool_name="search_products",
        input_data={"query": "running"},
        output_data={"results": [{"id": "p1", "name": "Shoe"}]},
        decision="FOUND_PRODUCTS",
        duration_ms=45.2,
        status="SUCCESS"
    )

    s2 = AgentTracingService.record_step(
        db=db,
        trace_id=trace_id,
        agent_trace_id=at.id,
        sequence_number=2,
        step_type="REASONING",
        decision="SUGGEST_TOP_RESULT",
        duration_ms=12.0,
        status="SUCCESS"
    )
    db.commit()

    # Complete trace
    completed = AgentTracingService.complete_agent_trace(
        db=db,
        agent_trace_id=at.id,
        status="SUCCESS",
        output_data={"response": "Here are your running shoes"},
        token_usage=240,
        tool_call_count=1
    )
    db.commit()

    assert completed.status == "SUCCESS"
    assert completed.tool_call_count == 1
    assert completed.token_usage == 240
    assert completed.latency_ms >= 0.0
    assert len(completed.steps) == 2
    assert completed.steps[0].tool_name == "search_products"

def test_shopping_agent_tool_observability(client: TestClient, db: Session, setup_test_data):
    """
    Test: Executing a message through ShoppingAgent records AgentTrace, AgentStep, and AuditEvent records.
    """
    m1_id = setup_test_data["m1"]
    session_id = "sess_trace_shop_01"
    trace_id = "trc_shop_exec_01"

    agent = ShoppingAgent(db=db, merchant_id=m1_id, session_id=session_id, trace_id=trace_id)
    response = agent.process_message("running shoes under 4000")
    db.commit()

    assert response.trace_id == trace_id

    # Check AgentTrace in DB
    at = db.query(AgentTrace).filter(AgentTrace.trace_id == trace_id).first()
    assert at is not None
    assert at.agent_id == "shopping_agent_v1"
    assert at.status == "SUCCESS"

    # Check AgentSteps in DB
    steps = db.query(AgentStep).filter(AgentStep.trace_id == trace_id).all()
    assert len(steps) >= 1
    assert steps[0].tool_name == "search_products"
    assert steps[0].status == "SUCCESS"
