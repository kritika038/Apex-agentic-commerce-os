# Phase 7: Audit Trail, Agent Trace & Observability

## Overview

The Agentic Commerce OS includes a production-oriented, database-backed, tamper-evident observability system. Every AI interaction, tool execution, catalog discovery, cart mutation, sales recommendation, purchase intent, policy decision, human approval, payment attempt, webhook event, and reconciliation action is correlated under a unified `trace_id`.

---

## Core Invariants

1. **Unified Correlation**: Every milestone across the AI, commerce, and payment lifecycle shares a persistent `trace_id`.
2. **Database-Backed Immutability**: Logs are not treated as the primary audit record. Authoritative audit events are persisted in the `audit_events` table. No normal application API endpoint allows `UPDATE` or `DELETE` on audit events.
3. **Cryptographic SHA-256 Hash Chaining**: Every `AuditEvent` includes a `previous_event_hash`, `sequence_number`, and `event_hash` generated over canonicalized, redacted JSON bytes and the previous hash.
4. **Fail-Closed Verification**: Any sequence gap, payload modification, event insertion, reordering, or fork invalidates the entire chain during verification.
5. **Trace-Head Concurrency Serialization**: Writes to a trace chain are serialized using `AuditTraceHead` with row-level locks (`SELECT ... FOR UPDATE`), preventing hash-chain forks during concurrent requests.
6. **Pre-Hash Recursive Redaction**: Sensitive keys (passwords, tokens, API keys, webhook secrets, card numbers, CVVs) are redacted recursively **before** payload canonicalization and hashing.
7. **Honest Metrics**: Observability metrics reflect actual database records; percentiles (such as p95) return `"N/A"` if there are fewer than 3 samples.

---

## Data Models

### 1. `AuditEvent`
- `id`: UUID primary key
- `merchant_id`: Tenant identifier
- `trace_id`: Correlated request trace identifier
- `session_id`, `purchase_intent_id`, `payment_transaction_id`, `authorization_id`, `approval_request_id`: Cross-stage correlation IDs
- `sequence_number`: Monotonically increasing sequence number per (merchant_id, trace_id)
- `actor_type`: `USER`, `AGENT`, `SYSTEM`, `PROVIDER`, `WEBHOOK`
- `actor_id`: ID of the acting agent, user, or service
- `action`: Specific operation performed (e.g. `AI_REQUEST`, `EVALUATE_POLICY`, `CREATE_PAYMENT_ORDER`)
- `event_type`: Category of the event
- `status`: Execution status (`SUCCESS`, `FAILED`, `DENIED`, `CAPTURED`, etc.)
- `previous_event_hash`: SHA-256 hash of the previous event (Genesis: 64 zeroes)
- `event_hash`: SHA-256 hash of canonicalized event payload + previous hash
- `metadata_json`: Sanitized metadata dictionary

### 2. `AuditTraceHead`
- `merchant_id`, `trace_id`: Primary composite key
- `latest_sequence_number`: Highest sequence number written to the chain
- `latest_event_hash`: SHA-256 hash of the latest event in the chain

### 3. `AgentTrace` & `AgentStep`
- `AgentTrace`: High-level execution metadata for AI agents (model, provider, token usage, total latency, tool call count, privacy hashes).
- `AgentStep`: Granular step breakdowns for each tool call and reasoning phase with duration, status, and input/output payloads.

---

## Canonical Hash Formula

For each event:
```python
canonical_dict = {
    "action": action,
    "actor_id": actor_id,
    "actor_type": actor_type,
    "created_at": created_at.isoformat(),
    "decision": decision,
    "error_code": error_code,
    "event_type": event_type,
    "merchant_id": merchant_id,
    "metadata_json": redact_sensitive_data(metadata_json),
    "new_state": new_state,
    "policy_result": policy_result,
    "previous_state": previous_state,
    "reason": reason,
    "resource_id": resource_id,
    "resource_type": resource_type,
    "risk_level": risk_level,
    "sequence_number": sequence_number,
    "status": status,
    "tool_name": tool_name,
    "trace_id": trace_id,
}

canonical_bytes = json.dumps(canonical_dict, sort_keys=True, separators=(',', ':')).encode('utf-8')
event_hash = hashlib.sha256(canonical_bytes + previous_event_hash.encode('utf-8')).hexdigest()
```

---

## API Endpoints

- `GET /api/v1/audit/traces/{trace_id}`: Reconstructs the complete lifecycle timeline, validates hash-chain integrity, and generates executive summaries.
- `GET /api/v1/audit/events`: Paginated event stream queryable by `trace_id`, `actor_type`, and `status`.
- `GET /api/v1/audit/agents/{agent_id}/traces`: Retrieves agent execution traces and tool step telemetry.
- `GET /api/v1/audit/metrics`: Computes aggregate execution counts, success rates, latency percentiles, and tool usage.
- `GET /api/v1/health`: Liveness probe for uptime monitoring.
- `GET /api/v1/ready`: Readiness probe verifying database connectivity and provider configuration without exposing credentials.

---

## Verification & Interactive Demo

Run the end-to-end trace verification script:
```bash
cd backend
PYTHONPATH=. ./venv/bin/python scripts/run_phase7_demo.py
```
