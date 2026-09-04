# AI-to-AI Commerce Protocol Specification

## 1. Overview & Philosophy

The **AI-to-AI Commerce Protocol** is a structured, machine-readable JSON-RPC/REST standard that allows autonomous AI buyer agents to discover products, negotiate, create purchase intents, and settle transactions with merchant systems—while deterministic policy and payment gateways retain absolute authority over money movement.

```
+-------------------------------------------------------------+
|                 AUTONOMOUS AI BUYER AGENT                   |
+-------------------------------------------------------------+
                               |
                               | (1) Structured JSON Protocol
                               v
+-------------------------------------------------------------+
|               AGENTIC COMMERCE CONTROL PLANE                |
|                                                             |
|  +--------------------+        +-------------------------+  |
|  |  Shopping Agent    |        |       Sales Agent       |  |
|  |  (Catalog Query)   |        |   (Recommendations)     |  |
|  +--------------------+        +-------------------------+  |
|            |                                |               |
|  +-------------------------------------------------------+  |
|  |           AGENT PERMISSION FIREWALL (Least-Privilege)  |  |
|  +-------------------------------------------------------+  |
|            |                                                |
|  +-------------------------------------------------------+  |
|  |           DETERMINISTIC POLICY & RISK ENGINE          |  |
|  +-------------------------------------------------------+  |
|            |                                                |
|  +-------------------------------------------------------+  |
|  |           HUMAN GOVERNANCE / APPROVAL GATE            |  |
|  +-------------------------------------------------------+  |
|            |                                                |
|  +-------------------------------------------------------+  |
|  |           TRANSACTION AUTHORIZATION MINT              |  |
|  +-------------------------------------------------------+  |
|            |                                                |
|  +--------------------+        +-------------------------+  |
|  | Razorpay Provider  |        | SHA-256 Audit Trail     |  |
|  | Settlement Boundary|        | Cryptographic Ledger    |  |
|  +--------------------+        +-------------------------+  |
+-------------------------------------------------------------+
```

---

## 2. Core Invariants & Security Guarantees

| Guarantee | Enforcement Mechanism |
| :--- | :--- |
| **Price Authority** | Strictly derived from PostgreSQL / SQLite database records. LLM / client price overrides are ignored. |
| **Stock & Inventory** | Real-time database locking; out-of-stock items cannot be converted to purchase intents. |
| **Payment Boundary** | Autonomous agents cannot directly invoke payment settlement. A valid, unexpired `TransactionAuthorization` is mandatory. |
| **Policy Engine** | Executes deterministic Python rules (Decimal money, velocity, risk limits) strictly outside LLM context. |
| **State Machine** | `UNKNOWN ≠ FAILED`: Gateway timeouts transition to `UNKNOWN` and block blind retries until active reconciliation resolves final state. |
| **Audit Ledger** | Append-only SHA-256 hash-chained event ledger with recursive secret redaction. |

---

## 3. Protocol Endpoints

### 3.1 Capability Discovery
**`GET /api/v1/protocol/capabilities`**

Allows an external AI buyer or autonomous agent to discover supported operations, currency constraints, and active security guarantees.

**Response Schema:**
```json
{
  "protocol_version": "1.0.0",
  "merchant_id": "merchant_demo_sports",
  "merchant_name": "Demo Sports Merchant",
  "supported_currency": "INR",
  "operations": [
    "discover",
    "recommend",
    "purchase_intent",
    "authorization_lookup",
    "payment_request"
  ],
  "capabilities": {
    "catalog_search": true,
    "inventory_validation": true,
    "authoritative_pricing": true,
    "contextual_recommendations": true,
    "structured_purchase_intents": true,
    "deterministic_policy_engine": true,
    "risk_scoring": true,
    "human_approval_workflow": true,
    "transaction_authorization": true,
    "payment_provider_abstraction": true,
    "cryptographic_audit_trail": true
  },
  "security_guarantees": {
    "price_authority": "DATABASE_GROUNDED",
    "inventory_authority": "DATABASE_GROUNDED",
    "payment_authority": "RESTRICTED_AUTHORIZATION_BOUNDARY",
    "audit_integrity": "SHA256_HASH_CHAINED",
    "tenant_isolation": "ENABLED"
  }
}
```

---

### 3.2 Product Discovery
**`POST /api/v1/protocol/discover`**

Allows autonomous AI agents to search and filter products matching constraints without relying on free-form chat.

**Request Schema:**
```json
{
  "query": "Running shoes",
  "category": "Footwear",
  "max_price": 5000.00,
  "currency": "INR",
  "trace_id": "trc_proto_sample_01"
}
```

**Response Schema:**
```json
{
  "session_id": "sess_proto_a1b2c3d4",
  "trace_id": "trc_proto_sample_01",
  "products": [
    {
      "id": "prod_running_01",
      "name": "Pro Running Shoes",
      "category": "Footwear",
      "price": 3499.00,
      "currency": "INR",
      "in_stock": true,
      "stock_quantity": 25,
      "description": "High performance carbon-plated running shoes"
    }
  ],
  "total_found": 1,
  "cart": [],
  "message": "Discovered 1 product(s) matching machine constraints."
}
```

---

### 3.3 Contextual Recommendations
**`POST /api/v1/protocol/recommend`**

Enables merchant `SalesAgent` to provide structured, grounded upsell and cross-sell suggestions to an AI buyer.

**Request Schema:**
```json
{
  "session_id": "sess_proto_a1b2c3d4",
  "buyer_preferences": {
    "category": "Accessories"
  },
  "trace_id": "trc_proto_sample_01"
}
```

**Response Schema:**
```json
{
  "session_id": "sess_proto_a1b2c3d4",
  "trace_id": "trc_proto_sample_01",
  "recommendations": [
    {
      "recommendation_id": "rec_socks_01",
      "type": "CROSS_SELL",
      "recommended_product_id": "prod_socks_01",
      "product_name": "Performance Socks",
      "product_price": 399.00,
      "currency": "INR",
      "reason": "Frequently bought together with Pro Running Shoes",
      "confidence": 0.92,
      "status": "SHOWN"
    }
  ]
}
```

---

### 3.4 Structured Purchase Intent
**`POST /api/v1/protocol/purchase-intent`**

Converts authoritative cart items into a server-validated `PurchaseIntent`. Calculates total amount exclusively from database records.

**Request Schema:**
```json
{
  "session_id": "sess_proto_a1b2c3d4",
  "buyer_id": "ai_buyer_agent_007",
  "constraints": {
    "max_price": 4000.00,
    "currency": "INR"
  },
  "trace_id": "trc_proto_sample_01"
}
```

**Response Schema:**
```json
{
  "purchase_intent_id": "pi_8f91a2bc",
  "merchant_id": "merchant_demo_sports",
  "buyer_id": "ai_buyer_agent_007",
  "cart_id": "cart_12345",
  "status": "CREATED",
  "requested_amount": 3499.00,
  "currency": "INR",
  "items": [
    {
      "product_id": "prod_running_01",
      "name": "Pro Running Shoes",
      "quantity": 1,
      "unit_price": "3499.00",
      "subtotal": "3499.00"
    }
  ],
  "expires_at": "2026-09-01T17:00:00Z",
  "trace_id": "trc_proto_sample_01"
}
```

---

### 3.5 Authorization Status Lookup
**`GET /api/v1/protocol/authorization/{purchase_intent_id}`**

Returns the current deterministic authorization state for a purchase intent:
- `NOT_EVALUATED`: Waiting for policy evaluation.
- `AUTHORIZED`: Approved; valid `authorization_id` available.
- `REQUIRES_APPROVAL`: Paused for human merchant operator approval.
- `DENIED`: Denied by policy rules or risk engine.
- `EXPIRED`: Time limit exceeded.

---

### 3.6 Payment Initiation Boundary
**`POST /api/v1/protocol/payment-request`**

Initiates payment order settlement. Amount and currency are derived **exclusively** from the backend `TransactionAuthorization` snapshot; client-supplied amount parameters are prohibited.

**Request Schema:**
```json
{
  "purchase_intent_id": "pi_8f91a2bc",
  "authorization_id": "auth_9910ab",
  "idempotency_key": "idemp_client_987654",
  "trace_id": "trc_proto_sample_01"
}
```

**Response Schema:**
```json
{
  "payment_transaction_id": "tx_payment_9988",
  "razorpay_order_id": "order_mock_112233",
  "amount": 3499.00,
  "currency": "INR",
  "status": "PAYMENT_PENDING",
  "receipt": "rcpt_pi_8f91a2bc",
  "trace_id": "trc_proto_sample_01",
  "created_at": "2026-09-01T16:45:00Z"
}
```
