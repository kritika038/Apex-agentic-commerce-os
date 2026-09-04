# Deterministic Policy Engine, Risk Engine & Human Approval

## 1. Overview & Core Philosophy

Phase 4 establishes the **Deterministic Financial Policy and Safety Layer** that sits between commerce **Purchase Intent** (Phase 3) and future **Payment Execution** (Phase 5).

$$\text{Purchase Intent} \longrightarrow \text{Deterministic Policy Engine} \longrightarrow \text{Agent Permission Check} \longrightarrow \text{Risk Assessment} \longrightarrow \text{Human Approval (if required)} \longrightarrow \text{Transaction Authorization}$$

### Strict Safety Boundaries:
* **The LLM can generate intent**: AI buyers and shopping agents can explore products, build carts, and register purchase intents.
* **The LLM cannot authorize financial actions**: All policy checks and risk calculations are 100% deterministic with **zero LLM calls**.
* **The LLM cannot modify financial policy**: Only authenticated merchant operators can create or update policies.
* **The LLM cannot grant itself permissions**: Agent capabilities are strictly enforced at the Tool Registry via database-backed normalized permissions.
* **Exact Decimal Arithmetic**: Monetary calculations never use floating-point types. Python `Decimal` and database `NUMERIC(12, 2)` guarantee zero rounding drift.
* **Financial Phase Boundary**: Phase 4 strictly terminates at `TransactionAuthorization` (`AUTHORIZED`). No Razorpay SDK, order creation, payment capture, or webhooks are executed in Phase 4.

---

## 2. Policy Engine Architecture & Rules

The `PolicyEngine` (`backend/app/policies/policy_engine.py`) deterministically validates every Purchase Intent against the merchant's active policy configuration:

| Check Rule | Evaluation Logic | Failure Action |
|---|---|---|
| `PURCHASE_INTENT_VALIDITY` | Verifies intent exists, belongs to merchant, and is not expired or rejected. | DENY |
| `MAX_TRANSACTION` | Enforces `requested_amount <= policy.max_transaction_amount` (e.g. ₹10,000.00). | DENY |
| `CURRENCY` | Verifies `currency == policy.allowed_currency` (e.g. `INR`). | DENY |
| `MAX_QUANTITY` | Verifies total item count in cart $\le$ `policy.max_quantity` (e.g. 5 items). | DENY |
| `MAX_DISCOUNT` | Verifies applied discounts $\le$ `policy.max_discount_percent` (e.g. 5.00%). | DENY |
| `INVENTORY_AVAILABLE` | Checks real-time stock levels in database for every line item. | DENY |
| `AGENT_PERMISSION` | Verifies that the invoking agent is active and scoped for commerce tools. | DENY |

---

## 3. Risk Engine (`backend/app/policies/risk_engine.py`)

Financial risk is calculated using transparent, deterministic rules:

* **`LOW`**:
  * `amount <= policy.low_risk_limit` (e.g. $\le$ ₹2,000.00)
  * Zero policy violations
  * Sufficient inventory and valid agent permissions
* **`MEDIUM`**:
  * `policy.low_risk_limit < amount <= policy.approval_threshold` (e.g. ₹2,000.00 < amount $\le$ ₹5,000.00)
  * Zero hard policy violations
* **`HIGH`**:
  * `amount > policy.approval_threshold` (e.g. amount > ₹5,000.00)
  * Or any hard policy violation detected

---

## 4. Human Approval Workflow & State Machine

When a transaction is flagged as `REQUIRES_APPROVAL` (due to exceeding `approval_threshold` or `HIGH` risk):

1. **`ApprovalRequest` Created**: An approval record is initialized with status `PENDING` and a 15-minute expiration window.
2. **Purchase Intent Preserved**: The `PurchaseIntent` remains in `CREATED` state awaiting merchant sign-off.
3. **Atomic Review in Console**:
   * **`POST /api/v1/approvals/{id}/approve`**: Authenticated merchant operator approves $\rightarrow$ atomically transitions to `APPROVED` $\rightarrow$ issues `TransactionAuthorization` (`AUTHORIZED`, 10 min expiration).
   * **`POST /api/v1/approvals/{id}/reject`**: Merchant operator rejects $\rightarrow$ transitions to `REJECTED` $\rightarrow$ marks `PurchaseIntent` as `REJECTED`.
4. **Race Condition Prevention**:
   * Attempting to approve an already approved/rejected request raises `409 Conflict`.
   * Expired approval requests cannot generate authorizations (`400 Bad Request`).

---

## 5. Policy Versioning & Audit Immutability

To guarantee reproducible financial audits, policies are **never updated in place**:

1. When a merchant modifies a policy (`PUT /api/v1/policies/{id}`), the current policy record is deactivated (`is_active = False`).
2. A new immutable `Policy` row is inserted with `version = previous_version + 1` and `is_active = True`.
3. Every `PolicyEvaluation` stores an **immutable JSON snapshot** of the exact parameters evaluated:
```json
{
  "policy_id": "pol_101",
  "policy_version": 1,
  "name": "Standard Commerce Policy",
  "max_transaction_amount": "10000.00",
  "approval_threshold": "5000.00",
  "low_risk_limit": "2000.00",
  "max_discount_percent": "5.00",
  "max_quantity": 5,
  "allowed_currency": "INR",
  "auto_approval_enabled": true,
  "authorization_expiration_minutes": 10
}
```
4. Subsequent policy updates never alter historical evaluation snapshots.

---

## 6. Normalized Agent Permissions & Least Privilege

Agent permissions are modeled in the database via normalized tables (`agents`, `permissions`, `agent_permissions`):

| Permission Name | Category | ShoppingAgent | SalesAgent | PaymentAgent |
|---|---|:---:|:---:|:---:|
| `READ_PRODUCTS` | Catalog | ✓ | ✓ | ✗ |
| `READ_INVENTORY` | Inventory | ✓ | ✓ | ✗ |
| `CREATE_CART` | Cart | ✓ | ✗ | ✗ |
| `READ_CART` | Cart | ✓ | ✓ | ✗ |
| `MODIFY_CART` | Cart | ✓ | ✗ | ✗ |
| `CALCULATE_CART` | Cart | ✓ | ✗ | ✗ |
| `RECOMMEND_PRODUCT` | Commerce | ✓ | ✗ | ✗ |
| `CREATE_RECOMMENDATION` | Commerce | ✗ | ✓ | ✗ |
| `CREATE_PAYMENT_ORDER` | Payment (Phase 5) | ✗ | ✗ | ✓ |
| `READ_PAYMENT_STATUS` | Payment (Phase 5) | ✗ | ✗ | ✓ |
| `MANAGE_POLICY` | Security (Human only) | ✗ | ✗ | ✗ |

---

## 7. Transaction Authorization Boundary (`TransactionAuthorization`)

`TransactionAuthorization` is the security contract consumed downstream by Phase 5:

```json
{
  "id": "auth_8372bf91",
  "merchant_id": "m_101",
  "purchase_intent_id": "pi_29384",
  "policy_evaluation_id": "eval_48291",
  "approval_request_id": "appr_19283",
  "status": "AUTHORIZED",
  "authorized_amount": "8500.00",
  "currency": "INR",
  "authorized_by": "user_admin_01",
  "authorized_at": "2026-09-01T09:30:00Z",
  "expires_at": "2026-09-01T09:40:00Z"
}
```

### Authorization Validation Service (`AuthorizationService`):
Phase 5 validates authorizations before initiating payment:
* Verifies `status == 'AUTHORIZED'`.
* Verifies `now < expires_at`.
* Enforces exact matching on `authorized_amount` and `currency` (preventing downstream price alteration).
