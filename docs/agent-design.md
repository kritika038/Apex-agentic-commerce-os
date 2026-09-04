# Agent Design & Architecture

## 1. End-to-End Agentic Commerce Pipeline

$$\text{Agent} \longrightarrow \text{Intent} \longrightarrow \text{Policy} \longrightarrow \text{Risk} \longrightarrow \text{Approval} \longrightarrow \text{Authorization} \longrightarrow \text{Future Payment}$$

1. **AI Buyer**: Initiates natural language shopping requirements with budget constraints (`max_price`, `quantity`, `category`).
2. **Shopping Agent (`ShoppingAgent`)**: Discovers merchant catalog items, inspects real-time inventory, and manages user cart.
3. **Sales Agent (`SalesAgent`)**: Contextually evaluates cart items and generates complementary cross-sell recommendations.
4. **Structured Purchase Intent (`PurchaseIntent`)**: Encapsulates the desired order with server-calculated Decimal amounts. Initial status: `CREATED`.
5. **Deterministic Policy Engine (`PolicyEngine`)**: Zero-LLM deterministic rule engine that evaluates `MAX_TRANSACTION`, `CURRENCY`, `MAX_QUANTITY`, `MAX_DISCOUNT`, `INVENTORY_AVAILABLE`, `AGENT_PERMISSION`.
6. **Risk Assessment (`RiskEngine`)**: Deterministic risk calculation (`LOW`, `MEDIUM`, `HIGH`).
7. **Human Approval (`ApprovalRequest`)**: Flags transactions exceeding thresholds for authenticated merchant review.
8. **Transaction Authorization (`TransactionAuthorization`)**: Exact-amount, time-bound authorization record that serves as the boundary for Phase 5 Razorpay settlement.

---

## 2. Agent Roles & Capabilities

### Shopping Agent
* Serves as natural language bridge between customer and catalog.
* Translates unstructured intent into structured queries.
* Scoped to: `READ_PRODUCTS`, `READ_INVENTORY`, `CREATE_CART`, `READ_CART`, `MODIFY_CART`, `CALCULATE_CART`, `RECOMMEND_PRODUCT`.

### Sales Agent
* Analyzes cart context and proposes upselling / cross-selling opportunities.
* Grounded in active merchant inventory; enforces anti-spam limits (max 2 recs/session, no duplicates).
* Scoped to: `READ_PRODUCTS`, `READ_INVENTORY`, `READ_CART`, `CREATE_RECOMMENDATION`.
* **Cannot modify cart directly, alter prices, or access payment tools.**

### Payment Agent (Phase 5 Boundary)
* Scoped strictly to: `CREATE_PAYMENT_ORDER`, `READ_PAYMENT_STATUS`, `RECONCILE_PAYMENT`.
* Strictly disabled from executing payments in Phase 4.

---

## 3. What the LLM Does vs. What Deterministic Code Does

| Layer | Responsibility | Mechanism |
|---|---|---|
| **LLM Reasoning** | Unstructured intent parsing, contextual tool selection, conversational explanations. | LLM Gateway / Mock Provider |
| **Catalog Facts** | Authoritative prices, active status, stock counts. | SQL database queries |
| **Cart & Financial Math** | Line item subtotals, deterministic total calculation. | Python `Decimal` arithmetic |
| **Policy Enforcement** | Limits, currency matching, max quantities, risk tiers. | Deterministic `PolicyEngine` (0 LLM calls) |
| **Financial Authorization** | Sign-off on high-risk transactions, issuing `TransactionAuthorization`. | Human merchant operators / backend |

---

## 4. Normalized Agent Permission Matrix

| Permission Name | Category | ShoppingAgent | SalesAgent | PaymentAgent | Merchant User |
|---|---|:---:|:---:|:---:|:---:|
| `READ_PRODUCTS` | Catalog | ✅ | ✅ | ❌ | ✅ |
| `READ_INVENTORY` | Inventory | ✅ | ✅ | ❌ | ✅ |
| `CREATE_CART` | Cart | ✅ | ❌ | ❌ | ✅ |
| `READ_CART` | Cart | ✅ | ✅ | ❌ | ✅ |
| `MODIFY_CART` | Cart | ✅ | ❌ | ❌ | ✅ |
| `CALCULATE_CART` | Cart | ✅ | ❌ | ❌ | ✅ |
| `RECOMMEND_PRODUCT` | Commerce | ✅ | ❌ | ❌ | ✅ |
| `CREATE_RECOMMENDATION` | Commerce | ❌ | ✅ | ❌ | ✅ |
| `CREATE_PAYMENT_ORDER` | Payment (Phase 5) | ❌ | ❌ | ✅ | ❌ |
| `READ_PAYMENT_STATUS` | Payment (Phase 5) | ❌ | ❌ | ✅ | ✅ |
| `MANAGE_POLICY` | Security | ❌ | ❌ | ❌ | ✅ |

---

## 5. Security Boundaries
1. **No Direct DB Access**: LLMs emit structured tool calls; they cannot formulate or execute SQL.
2. **No Client / LLM Price Authority**: Product prices and discount checks originate exclusively from server database snapshots.
3. **No Financial Self-Authorization**: Autonomous agents cannot authorize transactions, modify financial policies, or grant themselves permissions.
4. **Monetary Precision**: All monetary values are represented as `Decimal` / `NUMERIC(12, 2)` to eliminate floating-point drift.
5. **Strict Payment Separation**: Phase 4 ends at `TransactionAuthorization`. Payment execution occurs exclusively via Phase 5 Razorpay/Mock providers.

---

## 6. Observability & Agent Tracing (Phase 7)
1. **Unified Request Tracing**: Every AI message, tool execution, policy decision, approval, payment order, and webhook is tagged with a correlated `trace_id`.
2. **Agent Execution Telemetry**: `AgentTrace` records model identifier, provider, prompt/response tokens, total latency, and tool call frequency.
3. **Granular Step Logging**: `AgentStep` captures tool call inputs, outputs, execution duration, and agent reasoning decisions.
4. **Tamper-Evident Audit Ledger**: Every lifecycle milestone is hashed into a SHA-256 cryptographic chain stored in `audit_events`.
5. **Fail-Closed Verification**: The `AuditIntegrityService` detects sequence gaps, payload mutations, insertions, reordering, and hash forks across the entire lifecycle.

---

## 7. AI-to-AI Commerce Protocol & Control Plane (Phase 8)
1. **Machine-to-Machine JSON Contracts**: Autonomous AI buyers interact with merchants using formal Pydantic-validated REST endpoints (`/api/v1/protocol/*`) rather than free-form conversational parsing.
2. **Capability Discovery (`GET /api/v1/protocol/capabilities`)**: Machine-readable manifest declaring merchant currency, operations, and cryptographic security guarantees.
3. **Agent Permission Firewall (`GET /api/v1/agents/firewall`)**: Formally enforced least-privilege matrix proving that no agent (Shopping, Sales, External Buyer) possesses payment authorization or price alteration permissions.
4. **Executive Control Plane UI (`/dashboard/control-plane`)**: High-fidelity control console displaying live architecture pipelines, "Why Did AI Do This?" decision lineage, and 1-click interactive scenario simulations.
5. **A2A Protocol Explorer (`/dashboard/protocol`)**: Developer-friendly playground for testing discovery, recommendations, purchase intent minting, and authorization lookup.

---

## 8. Merchant Revenue Autopilot & Red-Team Security Lab (Phase 9)
1. **Controlled AI Revenue Optimization**: Scans merchant catalog in real time, generates AI copy/proposals, deterministically computes margin & discount costs, and requires operator sign-off before campaign execution.
2. **Strict Separation of Financial Authority**: AI reasoning produces suggestions and marketing copy; pure Python deterministic math and policy limits dictate all monetary amounts.
3. **Adversarial Security Harness**: Live testing environment validating 12 high-severity AI attack vectors (price tampering, prompt injection, privilege escalation, cross-tenant isolation, state machine bypass) against production endpoints.
4. **Flagship Demo Interface (`/demo`)**: Visual 10-step execution pipeline linking AI buyer intent formulation directly to cryptographic SHA-256 audit sealing.
