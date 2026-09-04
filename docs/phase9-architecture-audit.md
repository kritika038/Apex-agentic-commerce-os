# Phase 9 Architecture & Security Audit

## 1. Existing System Architecture (Phases 1–8)

Agentic Commerce OS is a deterministic multi-agent commerce infrastructure layer consisting of:
1. **Multi-Tenant Foundation (Phase 1)**: PostgreSQL/SQLite schema with strict `merchant_id` foreign keys, JWT auth, and row-level tenant isolation.
2. **AI Shopping Agent & Tool Sandbox (Phase 2)**: Non-authoritative LLM reasoning (`ShoppingAgent`) bound by explicit tool registry permissions (`search_products`, `add_to_cart`, `view_cart`).
3. **Sales Optimization & Purchase Intent (Phase 3)**: Complementary cross-sell recommendation engine (`SalesAgent`) generating server-authoritative `PurchaseIntent` records with Decimal math.
4. **Deterministic Policy & Risk Engine (Phase 4)**: Pure Python rule engine (`PolicyEngine`, `RiskEngine`) evaluating `MAX_TRANSACTION`, `CURRENCY`, `MAX_QUANTITY`, `MAX_DISCOUNT`, `INVENTORY_AVAILABLE`, issuing time-bound `TransactionAuthorization` or triggering human `ApprovalRequest`.
5. **Payment Provider Abstraction & Razorpay Settlement (Phase 5)**: `PaymentProvider` interface with `RazorpayProvider` and `MockPaymentProvider`. Strict authorization boundary, Decimal currency units, idempotency keys, and HMAC-SHA256 webhook verification.
6. **Failure Recovery & Active Reconciliation (Phase 6)**: Invariant `UNKNOWN ≠ FAILED`. Ambiguous timeouts transition to `UNKNOWN` and block blind retries until active reconciliation resolves final provider state.
7. **Tamper-Evident Audit Trail & Observability (Phase 7)**: Append-only SHA-256 hash-chained audit ledger (`AuditEvent`, `AuditTraceHead`), pre-hash secret scrubber, and `AgentTrace`/`AgentStep` telemetry.
8. **AI-to-AI Commerce Protocol & Control Plane (Phase 8)**: Structured REST/JSON protocol (`/api/v1/protocol/*`), Agent Permission Firewall (`/api/v1/agents/firewall`), and executive control console.

---

## 2. Reusable Services & Components for Phase 9

| Existing Service | Location | Phase 9 Reuse Mode |
| :--- | :--- | :--- |
| `Product` & `Inventory` models | `backend/app/database/models/` | Grounding revenue opportunity recommendations in real SQL inventory. |
| `SalesAgent` | `backend/app/agents/sales_agent.py` | Reusing cross-sell and complementary association heuristics. |
| `PolicyEngine` | `backend/app/policies/policy_engine.py` | Enforcing max discount (e.g. 5%), max velocity, and transaction limits on revenue proposals. |
| `RiskEngine` | `backend/app/policies/risk_engine.py` | Computing deterministic risk scores for simulated campaigns. |
| `ApprovalService` | `backend/app/services/approval_service.py` | Reusing human sign-off workflow before executing high-risk campaigns. |
| `PaymentService` | `backend/app/payments/service.py` | Reusing payment order creation, idempotency, and state machine during red-team attacks. |
| `AuditService` | `backend/app/services/audit_service.py` | Recording revenue generation, simulation, approval, execution, and red-team attack audit events on the SHA-256 hash chain. |
| `AuditIntegrityService` | `backend/app/services/audit_integrity_service.py` | Verifying audit ledger integrity and detecting intentional tampering in Attack 09. |
| `ProtocolService` | `backend/app/protocol/service.py` | Testing machine-to-machine attack boundaries (price tampering, prompt injection, invalid currency). |
| `RedactionEngine` | `backend/app/utils/redaction.py` | Scrubbing secrets from red-team attack payloads before persistence. |

---

## 3. Existing Security Boundaries to Preserve

1. **Database Grounding**: Product prices, stock counts, and discounts are computed server-side using `Decimal`. LLM outputs cannot modify catalog prices or database inventory directly.
2. **Zero Direct Financial Authority for Agents**: Autonomous agents (Shopping, Sales, External Buyer, Revenue Autopilot) cannot issue `TransactionAuthorization` or call payment gateways directly.
3. **Deterministic Policy Precedence**: Policy evaluation runs outside the LLM context. No prompt injection can override deterministic rules (e.g., a 23% discount request is rejected when policy limit is 5%).
4. **Idempotency & Concurrency**: Duplicate execution requests with identical keys are safely resolved without duplicate state mutation.
5. **Tenant Isolation**: Cross-merchant queries are strictly rejected with HTTP 404 / 403.

---

## 4. Phase 9 Integration Points

### A. Merchant Revenue Autopilot (`backend/app/revenue/`)
- `RevenueOpportunity` table linked to `merchants.id`.
- `RevenueOpportunityEngine`: Evaluates product catalog, historical purchase intents, and stock levels to discover high-margin cross-sells, bundles, and campaigns.
- `RevenueProposalEngine`: Generates controlled marketing copy while grounding all prices and discounts in deterministic database facts.
- `RevenueSimulator`: Deterministic simulation engine calculating Projected GMV, Discount Cost, Net Incremental Value, Inventory Impact, and Policy Compliance.
- `RevenueCampaignService`: Multi-stage approval workflow (`GENERATED` $\to$ `SIMULATED` $\to$ `POLICY_CHECK` $\to$ `PENDING_APPROVAL` $\to$ `APPROVED` $\to$ `EXECUTED`) with immediate pre-execution policy and stock re-validation.
- `RevenueMeasurementService`: Separates `SIMULATED` projections from `ACTUAL` measured uplift.

### B. AI Red-Team Security Lab (`backend/app/security_lab/`)
- `SecurityAttackResult` table tracking attack scenarios, attempted payloads, blocking layers, and correlated trace IDs.
- `RedTeamAttackRunner`: Executes 12 real production attacks against existing endpoints (`/protocol/*`, `/payments/*`, `/purchase-intents/*`, `/audit/*`) without mocking.
- Deterministic Security Score: `(passed_attacks / total_attacks) * 100`.

---

## 5. Risks Discovered & Mitigations

1. **Risk of Misrepresenting Simulated Uplift**:
   - *Mitigation*: All projected revenue figures are strictly labelled `SIMULATED`, `PROJECTED`, or `ESTIMATED`. Actual uplift defaults to `No actual uplift measured yet` until real transaction conversions occur.
2. **Risk of Stale Simulation Execution**:
   - *Mitigation*: The campaign execution service re-evaluates deterministic policy rules and live inventory counts atomically at the exact millisecond of execution.
3. **Risk of LLM Policy Hallucination in "Why Not AI?"**:
   - *Mitigation*: The "Why Not AI?" feature directly displays the `PolicyEngine` evaluation record and rule violation (`MAX_DISCOUNT_PERCENT: 23% > 5%`), proving zero-LLM deterministic authority.
