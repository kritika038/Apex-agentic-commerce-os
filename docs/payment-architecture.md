# Payment Architecture, Razorpay Test Mode & Settlement

## 1. Overview & Core Security Boundary

Phase 5 introduces the **Payment Execution and Settlement Layer**, connecting the deterministic authorization layer with real **Razorpay Test Mode** payment processing.

$$\text{Purchase Intent} \longrightarrow \text{Policy Engine} \longrightarrow \text{Risk Assessment} \longrightarrow \text{Human Approval (if required)} \longrightarrow \text{Transaction Authorization} \longrightarrow \text{Payment Service} \longrightarrow \text{Razorpay Test Mode} \longrightarrow \text{Webhook / Reconciliation} \longrightarrow \text{CAPTURED}$$

### Absolute Security Principles:
1. **No Authorization, No Payment**: Razorpay will **never** receive an order creation request unless there is an active, unexpired, unrevoked `TransactionAuthorization` (`status == AUTHORIZED`).
2. **Server-Authoritative Amounts**: Payment amounts and currencies are strictly derived from `TransactionAuthorization.authorized_amount` in the backend database. Client-submitted prices or amounts are unconditionally ignored and rejected.
3. **No Direct Frontend State Mutation**: The frontend client can **never** directly set a payment to `CAPTURED`. Only server-side webhook verification or authoritative provider polling can transition a transaction to `CAPTURED`.
4. **Test Mode Enforcement**: `RAZORPAY_MODE=test` is enforced. Live keys (`rzp_live_...`) are rejected by the provider to eliminate any risk of real financial charging during development/testing.
5. **Exact Decimal Monetary Arithmetic**: Python `Decimal` and database `NUMERIC(12, 2)` are used internally. Conversions to integer minor units (paise) are executed centrally with zero floating-point math.

---

## 2. Payment Provider Abstraction

All business logic in `PaymentService` (`backend/app/payments/service.py`) depends strictly on the `PaymentProvider` interface (`backend/app/payments/provider.py`), completely isolating the application from direct vendor SDK couplings:

```
                  ┌───────────────────────────────┐
                  │       PaymentService          │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │   PaymentProvider Interface   │
                  └──────────────┬────────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
  ┌─────────────────────────────┐ ┌─────────────────────────────┐
  │      RazorpayProvider       │ │     MockPaymentProvider     │
  │ (Official Test Mode API/SDK)│ │ (Deterministic CI/Simulations)
  └─────────────────────────────┘ └─────────────────────────────┘
```

### Methods Enforced:
* `create_order(amount_minor, currency, receipt, notes) -> OrderResult`
* `fetch_order(order_id) -> OrderResult`
* `fetch_payment(payment_id) -> PaymentResult`
* `verify_webhook_signature(raw_body, signature, secret) -> bool`

---

## 3. Database Schema & Constraints

### `PaymentTransaction` (`payment_transactions`)
* `id`: UUID Primary Key
* `merchant_id`: Foreign Key to `merchants.id` (Indexed)
* `purchase_intent_id`: Foreign Key to `purchase_intents.id` (Indexed)
* `authorization_id`: Foreign Key to `transaction_authorizations.id` (Indexed)
* `razorpay_order_id`: Gateway Order ID (Indexed)
* `razorpay_payment_id`: Gateway Payment ID (Indexed)
* `amount`: `NUMERIC(12, 2)` (Exact Decimal)
* `currency`: `String` (e.g. `INR`)
* `status`: Current state machine status
* `idempotency_key`: Client idempotency key
* `receipt`: Deterministic receipt reference (`rcpt_<intent>_<idemp>`)
* **Constraint**: `UNIQUE(merchant_id, idempotency_key)` to enforce race-safe idempotency.

### `WebhookEvent` (`webhook_events`)
* `id`: UUID Primary Key
* `event_id`: Unique `x-razorpay-event-id` (Indexed)
* `event_type`: Event name (`payment.captured`, `payment.failed`, `order.paid`)
* `payload_hash`: SHA-256 hash of raw payload bytes
* `payload`: Full JSON payload
* `processing_status`: `RECEIVED`, `PROCESSED`, `DUPLICATE`, `FAILED`, `IGNORED`
* **Constraint**: `UNIQUE(event_id)` to deduplicate webhooks.

---

## 4. Payment State Machine & Transitions

The state machine (`backend/app/payments/state_machine.py`) manages all payment lifecycles:

```
[CREATED] ──▶ [ORDER_CREATING] ──┬──▶ [ORDER_CREATED] ──▶ [PAYMENT_PENDING] ──▶ [CAPTURED] (Terminal)
                                 │                            │
                                 ├──▶ [UNKNOWN] ──▶ [RECONCILING]
                                 │                            │
                                 └──▶ [FAILED] (Terminal) ◀───┘
```

### Out-of-Order Webhook Safety:
Razorpay webhooks may arrive out of chronological order. If a transaction has reached `CAPTURED`, a subsequent delayed `payment.failed` event is safely ignored and will never downgrade the settled terminal status.

---

## 5. Webhook Signature Verification & Deduplication

Webhooks received at `POST /api/v1/webhooks/razorpay` undergo strict multi-stage verification:

1. **Raw Body Integrity**: The raw request body (`request.body()`) is read directly as bytes.
2. **HMAC-SHA256 Verification**:
   $$\text{Expected Signature} = \text{HMAC-SHA256}(\text{webhook\_secret}, \text{raw\_body})$$
   Signatures are compared using constant-time comparison (`hmac.compare_digest`). Invalid signatures return `401 Unauthorized` with zero database state changes.
3. **Event Deduplication**: The `X-Razorpay-Event-Id` header is checked against the database. If already processed, the webhook is immediately acknowledged with `200 OK` without duplicate processing.

---

## 6. Payment Reconciliation (`PaymentReconciliation`)

When an order creation request encounters a network timeout, the transaction transitions to `UNKNOWN`.

* **No Blind Retries**: The system does **not** create another Razorpay order.
* **Authoritative Gateway Inquiry**: `PaymentReconciliation.reconcile_transaction` queries Razorpay (`fetch_order` / `fetch_payment`) to determine ground truth:
  * If paid $\rightarrow$ `CAPTURED`
  * If created/pending $\rightarrow$ `ORDER_CREATED` / `PAYMENT_PENDING`
  * If failed $\rightarrow$ `FAILED`

---

## 7. Environment Setup & Configuration

Configure in `backend/.env`:

```env
# Payment Provider Mode ("razorpay" for real test mode, "mock" for local tests)
PAYMENT_PROVIDER=mock
RAZORPAY_MODE=test

# Razorpay Test Mode Credentials
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxxxxxxxx
```

Official Razorpay References:
* [Razorpay Orders API Documentation](https://razorpay.com/docs/api/orders/)
* [Razorpay Webhooks & Signature Verification](https://razorpay.com/docs/webhooks/)
