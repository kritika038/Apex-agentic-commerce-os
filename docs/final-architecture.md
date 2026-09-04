# Agentic Commerce OS — Final Production Architecture

## 1. Multi-Tier Control Plane Architecture

The **Agentic Commerce OS** is engineered as a 5-tier architecture separating conversational AI intelligence from deterministic financial execution and cryptographic audit verification.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. AI REASONING & PROTOCOL LAYER                                            │
│   • Autonomous AI Buyer (Protocol /protocol)                                │
│   • Shopping Assistant Agent (Tool-Bound)                                   │
│   • Merchant Sales Agent (Contextual Cross-Sells)                           │
│   • Revenue Autopilot Proposal Engine (Marketing Copy & Rationale)          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Machine-Readable DTO / Structured Intent
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. DETERMINISTIC CONTROL & POLICY LAYER                                     │
│   • Agent Permission Firewall (Least-Privilege Tool Execution)              │
│   • Deterministic Policy Engine (Max Amount, Margin Ceiling, Currency)      │
│   • Risk Evaluation Engine (Low / Medium / High Risk Scoring)               │
│   • Server-Authoritative Price & Inventory Validation (Decimal Precision)   │
│   • Revenue Deterministic Simulator (Math & Margin Constraints)             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Policy Decision & Risk Classification
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. HUMAN GOVERNANCE & AUTHORIZATION LAYER                                   │
│   • Merchant Operator Approval Gate (High-Risk & Clearance Review)          │
│   • TransactionAuthorization Mint (Exact-Amount, 15-Min Time-Bound Snapshot)│
│   • Cryptographic Authorization Freeze (DB-Backed Immutable Payload)        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Validated Authorization Token
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. PAYMENT SETTLEMENT & FAILURE RECOVERY LAYER                              │
│   • Abstract PaymentProvider (Razorpay Test Mode / Mock Payment Provider)   │
│   • Payment State Machine (Enforces UNKNOWN != FAILED, Terminal Locks)      │
│   • Payment Idempotency Engine (Duplicate Key & Double-Spend Defense)       │
│   • HMAC-SHA256 Webhook Verification & Deduplication                        │
│   • Active Reconciliation Engine (Gateway Polling & State Convergence)      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Correlated Trace ID Telemetry
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. CRYPTOGRAPHIC TRUST & OBSERVABILITY LAYER                                │
│   • SHA-256 Tamper-Evident Hash Chain (Genesis Block, Sequence Locking)     │
│   • Recursive Pre-Hash Secret Redaction (Zero Secret Leakage)               │
│   • End-to-End Trace Lineage ("Why Did AI Do This?", "Why Not AI?")        │
│   • Red-Team Adversarial Security Lab (12 Attack Interceptions)             │
│   • Flagship Executive Demo Runner (/demo)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Architectural Invariants

### Invariant 1: Separation of Reasoning vs. Financial Authority
- **AI agents** can discover, propose, simulate, recommend, and reason.
- **AI agents CANNOT** set authoritative prices, execute payments directly, modify policies, approve high-risk campaigns, bypass inventory, or alter audit history.

### Invariant 2: `UNKNOWN ≠ FAILED`
- Network timeouts, gateway connection drops, or ambiguous provider responses transition transactions to `UNKNOWN`.
- The control plane **blocks blind duplicate retries** until active reconciliation inspects provider ground truth and resolves the state deterministically.

### Invariant 3: Server-Authoritative Money Movement
- Payment orders passed to payment gateways derive their minor unit amounts ($₹ \times 100$) strictly from the database-backed `TransactionAuthorization` record. Client overrides (`amount=1.00`) are rejected or ignored.

### Invariant 4: Tamper-Evident SHA-256 Audit Trail
- Every transaction, agent step, policy evaluation, approval, and payment event is chained into an immutable SHA-256 ledger:
  $$\text{Event Hash}_n = \text{SHA-256}\left(\text{CanonicalRedactedPayload}_n + \text{Event Hash}_{n-1}\right)$$
- Any database-level alteration, deletion, or sequence gap causes verification to fail immediately.

---

## 3. Technology Stack & Deployment Model

- **Backend:** FastAPI (Python 3.10+), SQLAlchemy ORM, Pydantic v2 validation, Pure Python `Decimal` arithmetic.
- **Database:** SQLite (local / fast deterministic tests) / PostgreSQL (production multi-tenant concurrency).
- **Payment Providers:** Razorpay Test Mode API (`RazorpayProvider`) + Deterministic Local Simulator (`MockPaymentProvider`).
- **Frontend Console:** Next.js 14 App Router, TypeScript, TailwindCSS, Lucide Icons, Glassmorphic UI theme.
