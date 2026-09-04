# Agent & Role Permission Firewall Matrix

## 1. Overview & Least-Privilege Policy

The **Agentic Commerce OS** enforces strict separation between conversational AI agents and financial execution authority. No single autonomous agent or external actor is granted unbounded access.

---

## 2. Definitive Role & Agent Permission Matrix

| Permission Name | Category | `ShoppingAgent` | `SalesAgent` | `ExternalAIBuyer` | `PaymentAgent` | `MerchantUser` (Admin) | `System Core` |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `READ_PRODUCTS` | Catalog | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| `READ_INVENTORY` | Inventory | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| `CREATE_CART` | Cart | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| `READ_CART` | Cart | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| `MODIFY_CART` | Cart | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| `CALCULATE_CART` | Cart | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| `RECOMMEND_PRODUCT` | Commerce | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| `CREATE_RECOMMENDATION`| Commerce | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ |
| `CREATE_PURCHASE_INTENT`| Commerce | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |
| `READ_AUTHORIZATION_STATUS`| Governance| ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |
| `AUTHORIZE_TRANSACTION`| Governance| ❌ | ❌ | ❌ | ❌ | ✅ *(Approval Gate)*| ✅ *(Low Risk Auto)*|
| `MANAGE_POLICY` | Security | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `CREATE_PAYMENT_ORDER` | Settlement | ❌ | ❌ | ❌ | ✅ | ❌ *(Via Auth)* | ✅ |
| `READ_PAYMENT_STATUS` | Settlement | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `RECONCILE_PAYMENT` | Settlement | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `READ_AUDIT_TRAIL` | Observability | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| `MUTATE_AUDIT_LOGS` | Ledger | ❌ | ❌ | ❌ | ❌ | ❌ *(Immutable)* | ❌ *(Immutable)* |

---

## 3. Sandboxed Agent Profiles

### Profile 1: `ShoppingAgent`
- **Isolation Level:** `SANDBOXED_CATALOG_CART`
- **Scope:** Natural language bridge between customer requirements and active merchant catalog.
- **Allowed Tools:** `search_products`, `get_product_stock`, `add_to_cart`, `view_cart`, `calculate_cart_total`.
- **Forbidden Actions:** Cannot approve transactions, modify prices, bypass stock, or interact with payment gateways.

### Profile 2: `SalesAgent`
- **Isolation Level:** `READ_ONLY_RECOMMENDATIONS`
- **Scope:** Contextual cross-selling and upselling based on active cart items.
- **Allowed Tools:** `search_products`, `get_product_stock`, `view_cart`, `generate_cross_sell`.
- **Forbidden Actions:** Cannot directly mutate cart items, change product pricing, or initiate purchases.

### Profile 3: `ExternalAIBuyer` (A2A Commerce Protocol)
- **Isolation Level:** `MACHINE_TO_MACHINE_SANDBOX`
- **Scope:** External autonomous AI agent querying catalog and expressing structured purchase intents.
- **Allowed Operations:** `discover`, `recommend`, `purchase_intent`, `authorization_lookup`.
- **Forbidden Actions:** Cannot authorize transactions, override merchant policies, or set arbitrary order prices.

### Profile 4: `PaymentAgent`
- **Isolation Level:** `GATED_AUTHORIZATION_BOUNDARY`
- **Scope:** Backend payment service communicating with payment gateway providers (Razorpay / Mock).
- **Allowed Tools:** `create_provider_order`, `fetch_payment_status`, `reconcile_transaction`.
- **Invariant:** Execution is strictly gated on a cryptographically verified `TransactionAuthorization` snapshot.

---

## 4. Immutable Audit & Ledger Constraints
- **Audit Tampering:** Neither users nor system administrators can modify or delete existing records in `audit_events`.
- **Cryptographic Hash Chain:** Every audit event entry cryptographically seals the previous event hash using SHA-256. Any database-level row alteration immediately invalidates the chain verification.
