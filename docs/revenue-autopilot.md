# Merchant Revenue Autopilot — Architecture & Control Plane Specification

## 1. Overview & Core Philosophy

The **Merchant Revenue Autopilot** transforms the Agentic Commerce OS into a proactive, revenue-optimizing control plane. It automatically discovers commercially useful growth opportunities across a merchant's active product catalog (cross-sells, upsells, bundles, and clearance campaigns), formulates AI-assisted marketing pitches, deterministically simulates financial outcomes under merchant margin constraints, and routes them through mandatory human governance before safe atomic execution.

```
┌───────────────────────────┐     ┌────────────────────────────┐     ┌────────────────────────────┐
│   Opportunity Engine      │ ──> │    AI Proposal Engine      │ ──> │  Deterministic Simulator   │
│  (Catalog & Stock Scan)   │     │ (Copy & Rationale Pitch)   │     │ (Math, Margin & Policy)    │
└───────────────────────────┘     └────────────────────────────┘     └──────────────┬─────────────┘
                                                                                    │
                                  ┌────────────────────────────┐                    ▼
                                  │      Audit & Tracing       │ <── ┌────────────────────────────┐
                                  │  (SHA-256 Tamper-Evident)  │     │   Merchant Operator Gate   │
                                  └────────────────────────────┘     │   (Human Sign-off Review)  │
                                                ▲                    └──────────────┬─────────────┘
                                                │                                   │
                                  ┌─────────────┴──────────────┐                    │
                                  │    Measurement Service     │ <──────────────────┘
                                  │ (Simulated vs Actual GMV)  │   (Atomic Execution)
                                  └────────────────────────────┘
```

---

## 2. Separation of Reasoning vs. Financial Authority

A central tenet of the Agentic Commerce OS is that **Autonomous Commerce Does Not Require Autonomous Financial Authority**.

| Dimension | AI Reasoning Layer (LLM / Heuristic) | Deterministic Financial Control Plane (Server Core) |
| :--- | :--- | :--- |
| **Catalog Analysis** | Discovers semantic affinity between products | Grounds products in active SQL database records |
| **Messaging** | Drafts promotional copy and customer pitches | Enforces schema validation and character constraints |
| **Discounting** | Proposes discount percentages (e.g. 23%) | Evaluates deterministic policy ceiling (e.g. max 5%) |
| **Pricing** | Has **zero authority** to set prices | Dictates exact unit prices and monetary Decimal totals |
| **Inventory** | Suggests volume targets | Performs real-time pre-execution lock on stock quantity |
| **Execution** | Cannot trigger payments or campaigns | Requires explicit operator approval + idempotency token |

---

## 3. Subsystem Components

### A. Opportunity Discovery Engine (`app.revenue.opportunity_engine`)
- Queries active merchant products and current warehouse inventory.
- Filters out out-of-stock items (`stock_quantity <= 0`).
- Generates 4 opportunity categories:
  1. `CROSS_SELL`: Identifies complementary categories (e.g. Running Shoes + Performance Socks).
  2. `UPSELL`: Discovers higher-tier variants within the same product vertical.
  3. `BUNDLE`: Pairs complementary equipment into discounted starter sets.
  4. `CAMPAIGN`: Identifies slow-moving or excess inventory for controlled promotional acceleration.

### B. AI Proposal Engine (`app.revenue.proposal_engine`)
- Generates structured marketing copy, customer-facing notifications, and commercial rationale.
- Explicitly separates **AI creative messaging** from **Server-Authoritative Facts** (unit prices, stock availability, and policy ceiling).

### C. Pure-Python Deterministic Simulator (`app.revenue.simulator`)
- Operates strictly with Python standard library `Decimal` math.
- Formulas:
  $$\text{Baseline GMV} = \sum (\text{Unit Price} \times \text{Target Orders})$$
  $$\text{Discount Cost} = \text{Baseline GMV} \times \left(\frac{\text{Discount \%}}{100}\right)$$
  $$\text{Projected Incremental GMV} = \text{Baseline GMV} - \text{Discount Cost}$$
  $$\text{Net Incremental Value} = \text{Incremental GMV} \times \text{Confidence Score}$$
- Enforces strict policy checking:
  - If $\text{Discount \%} > \text{Policy.max\_discount\_percent}$, marks `policy_compliant = False` and labels as `HIGH RISK`.

### D. Campaign Governance & Execution (`app.revenue.campaign_service`)
- Enforces state machine transitions: `GENERATED` $\to$ `SIMULATED` $\to$ `PENDING_APPROVAL` $\to$ `APPROVED` $\to$ `EXECUTED` (or `REJECTED`).
- Live re-validation: Before executing, re-checks that target products remain in-stock and active policy has not tightened.
- Cryptographic audit event logging on every state change.

### E. Measurement & Uplift Service (`app.revenue.measurement_service`)
- Strictly isolates `SIMULATED / PROJECTED` metrics from `ACTUAL EXECUTED` revenue.
- Prevents hypothetical AI projections from corrupting merchant accounting records.

---

## 4. API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/v1/revenue/opportunities` | `GET` | Lists all discovered revenue opportunities for merchant |
| `/api/v1/revenue/opportunities/generate` | `POST` | Scans catalog and generates grounded revenue opportunities |
| `/api/v1/revenue/opportunities/{id}` | `GET` | Returns opportunity details with AI proposal vs server facts |
| `/api/v1/revenue/simulate` | `POST` | Runs deterministic "What-If?" revenue and policy simulation |
| `/api/v1/revenue/opportunities/{id}/approve` | `POST` | Merchant operator approval gate |
| `/api/v1/revenue/opportunities/{id}/reject` | `POST` | Merchant operator rejection with mandatory reason |
| `/api/v1/revenue/opportunities/{id}/execute` | `POST` | Atomic execution with live inventory re-validation |
| `/api/v1/revenue/metrics` | `GET` | Returns aggregated simulated vs actual revenue metrics |
| `/api/v1/revenue/experiments` | `GET` | Lists active and executed growth campaigns |
