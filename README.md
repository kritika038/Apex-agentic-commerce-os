# APEX — Governed Agentic Commerce OS

> **Razorpay AI Buildathon 2026 · Track 01 — AI Growth & Agentic Commerce**

**Apex** is an AI-native commerce platform where **AI agents discover products, negotiate offers and identify growth opportunities — while deterministic policies, customer authorization and cryptographic audit controls govern money.**

### 🌐 Try Apex

- **Live Storefront:** https://apex-agentic-commerce-os-k7xe-phi.vercel.app/shopping
- **Judge Demo:** https://apex-agentic-commerce-os-k7xe-phi.vercel.app/demo
- **Repository:** https://github.com/kritika038/Apex-agentic-commerce-os

---

## 🚀 What Apex Does

### 1. AI Buyer Agent
Natural-language shopping becomes a structured commerce intent.

- Understands product, quantity, budget, category and constraints
- Searches a grounded, agent-readable catalog
- Preserves context across multi-turn shopping
- Can initiate governed purchase intents

### 2. Buyer ↔ Merchant Agent Negotiation
AI agents can negotiate commerce terms instead of relying only on fixed checkout flows.

- Buyer proposes a target price
- Merchant Agent evaluates the request against merchant policy
- Agent can accept, counter or reject
- Human merchant approval is required when policy demands it
- Offers have expiry, inventory revalidation and immutable pricing snapshots

### 3. Governed Agentic Payments
**AI autonomy never equals unrestricted financial authority.**

```text
AI Intent → Policy Evaluation → Offer → Human/Customer Authorization
→ Razorpay Checkout → Signature Verification → Order
```

- Server-authoritative prices and amounts
- Deterministic discount/quantity limits
- Razorpay Test Mode integration
- HMAC-SHA256 payment verification
- Idempotent payment/order handling
- No client-side authority over money

### 4. AI Growth & Revenue Agents
Merchant-side AI identifies actionable growth opportunities from live commerce data.

- Revenue insights
- Cross-sell / upsell opportunities
- Basket-affinity analysis
- Campaign simulation
- Inventory and sales signals
- Merchant approval before governed campaign execution

### 5. AI Shopping & Price Intelligence
A marketplace-style shopping experience with grounded product discovery.

- Natural-language AI Shopping Assistant
- Product/category/search filters
- Variant-aware catalog
- Verified external price comparison where evidence exists
- Price history based on actual observations
- No fabricated prices, stock or retailer offers

### 6. AI Virtual Try-On
Clothing PDPs include AI Virtual Try-On using **FASHN VTON v1.5**.

- Live camera or photo upload
- Apparel-only eligibility
- Real image generation rather than a visual overlay
- Local Apple Silicon/MPS inference for development
- Hugging Face ZeroGPU provider for the competition deployment path

### 7. Trust, Governance & Auditability
Every important agentic action is observable and explainable.

- Deterministic policy engine
- Customer / merchant role separation
- Multi-tenant authorization
- Approval workflows
- Transaction governance states
- Trace IDs and observability
- Tamper-evident SHA-256 audit hash chain

### 8. Authentication & Role Security

- Google OAuth authentication
- Server-authoritative customer/merchant roles
- Protected merchant operations
- Customer data isolation
- No trust in browser-supplied role, price or identity fields

---

## 🧠 Core Architecture

```text
Customer / AI Buyer
        ↓
AI Intent & Catalog Discovery
        ↓
Buyer Agent ↔ Merchant Agent
        ↓
Deterministic Governance / Merchant Policy
        ↓
Human Merchant Approval (when required)
        ↓
Customer Acceptance
        ↓
Razorpay Test Mode
        ↓
Server Verification + Order
        ↓
SHA-256 Audit Ledger
```

**Design principle:** AI reasons and proposes. Deterministic services decide what is allowed. Humans/customers authorize financial actions.

---

## 🛡️ Security by Design

Apex is built around a strict **AI reasoning vs. financial authority** boundary.

- Price tampering is rejected because checkout amounts come from server state
- Excessive discounts are hard-blocked by deterministic policy
- Unauthorized offer acceptance is rejected
- Cross-tenant merchant access is blocked
- Expired offers cannot be paid
- Inventory is revalidated before payment
- Duplicate payments are protected with idempotency/state controls
- Audit-chain mutations are detectable through SHA-256 verification

---

## 🎬 3-Minute Judge Flow

Open **[Judge Demo](https://apex-agentic-commerce-os-k7xe-phi.vercel.app/demo)** and run the canonical scenario:

```text
AI Buyer Intent
→ Grounded Product Discovery
→ Merchant Policy
→ AI Counter-Offer
→ Merchant Approval
→ Customer Acceptance
→ Governance Authorization
→ Razorpay Test Checkout
→ CAPTURED
→ Order Confirmation
→ SHA-256 Audit Trace
```

The demo also includes:

- **Failure Demo:** excessive discount is rejected before payment
- **Red-Team Demo:** client attempts to tamper with the payment amount; server authority wins
- **Agent Protocol View:** inspect machine-readable agent actions and governance decisions
- **Human View:** follow the same flow in plain language

---

## 🔧 Technology

**Frontend:** Next.js 14 · React · TypeScript · TailwindCSS  
**Backend:** FastAPI · Python · Pydantic · SQLAlchemy  
**Database:** PostgreSQL / SQLite-compatible architecture  
**AI:** Buyer Agent · Merchant Agent · Revenue/Growth Agents · LLM gateway  
**Payments:** Razorpay Checkout + server-side order creation + HMAC verification  
**VTO:** FASHN VTON v1.5 · PyTorch · MPS / Hugging Face ZeroGPU  
**Security:** JWT/OAuth · RBAC · tenant isolation · HMAC · SHA-256 audit chain  
**Deployment:** Vercel frontend · Render backend/database · Hugging Face VTO

---

## 📊 Validation

Latest project validation includes:

- **564 backend tests passed**
- **5 tests skipped** for external/live dependencies
- **0 backend test failures**
- **29/29 frontend routes compiled successfully**
- Dedicated regression coverage for catalog deduplication, VTO, negotiation, governance and payments

---

## 📁 Repository Structure

```text
Apex-agentic-commerce-os/
├── backend/      # FastAPI API, agents, governance, payments, database, tests
├── frontend/     # Next.js customer storefront, merchant OS and judge demo
├── hf-vton/      # Hugging Face ZeroGPU VTO Space
└── README.md
```

---

## 🎯 The Core Idea

> **Apex makes commerce agentic without making money uncontrolled.**

AI agents can **discover → reason → negotiate → recommend → act**.

Deterministic governance ensures they **cannot silently exceed financial authority**.

Every important transition can be inspected, verified and audited.
