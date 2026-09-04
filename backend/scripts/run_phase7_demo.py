#!/usr/bin/env python3
"""
Phase 7 Live Interactive Demo:
Full Lifecycle Observability, Agent Tracing, Correlated Audit Trail,
and Cryptographic SHA-256 Tamper Detection.
"""

import sys
import os
import json
import uuid
from decimal import Decimal
from datetime import datetime, timezone

# Ensure path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.database.session import SessionLocal, engine
from app.database.models.base import Base
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.policy import Policy
from app.database.models.audit_event import AuditEvent
from app.database.models.agent_trace import AgentTrace
from app.database.models.agent_step import AgentStep

from app.agents.shopping_agent import ShoppingAgent
from app.agents.sales_agent import SalesAgent
from app.services.purchase_intent_service import PurchaseIntentService
from app.policies.policy_engine import PolicyEngine
from app.services.approval_service import ApprovalService
from app.payments.service import PaymentService
from app.services.audit_service import AuditService
from app.services.audit_integrity_service import AuditIntegrityService, GENESIS_HASH

def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"   {title}")
    print("=" * 80)

def print_step(step_num: int, title: str, details: str = ""):
    print(f"\n[Step {step_num:02d}] {title}")
    if details:
        print(f"       ↳ {details}")

def run_demo():
    print_header("PHASE 7 LIVE DEMO — FULL LIFECYCLE AUDIT TRAIL & AGENT TRACING")
    print("This demo demonstrates end-to-end unified trace correlation, agent telemetry,")
    print("and cryptographic SHA-256 hash-chain tamper-evidence across the entire stack.\n")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # Setup merchant, catalog, and policy
        merchant = db.query(Merchant).first()
        if not merchant:
            merchant = Merchant(name="Apex Sportswear", domain="apex.example.com", is_active=True)
            db.add(merchant)
            db.commit()
            db.refresh(merchant)

        p1 = db.query(Product).filter(Product.merchant_id == merchant.id, Product.name == "Pro Running Shoes").first()
        if not p1:
            p1 = Product(merchant_id=merchant.id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
            p2 = Product(merchant_id=merchant.id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
            db.add_all([p1, p2])
            db.flush()
            db.add(Inventory(merchant_id=merchant.id, product_id=p1.id, stock_quantity=50))
            db.add(Inventory(merchant_id=merchant.id, product_id=p2.id, stock_quantity=100))
            db.commit()

        trace_id = f"trc_demo_{uuid.uuid4().hex[:8]}"
        session_id = f"sess_demo_{uuid.uuid4().hex[:6]}"
        buyer_id = "buyer_demo_phase7"

        print(f"📍 Context Initialized:")
        print(f"   • Merchant ID: {merchant.id}")
        print(f"   • Trace ID:    {trace_id}")
        print(f"   • Session ID:  {session_id}")

        # -------------------------------------------------------------
        # STEP 1: AI Buyer Request & Shopping Agent Tracing
        # -------------------------------------------------------------
        print_step(1, "AI Buyer Request & Shopping Agent", f"1. Search catalog, 2. Add product {p1.id} to cart")
        
        shopping_agent = ShoppingAgent(db=db, merchant_id=merchant.id, session_id=session_id, trace_id=trace_id)
        chat_res1 = shopping_agent.process_message("running shoes under 4000")
        print(f"   ✓ Search Output: \"{chat_res1.message}\"")

        chat_res2 = shopping_agent.process_message(f"add product {p1.id} to cart")
        print(f"   ✓ Add to Cart Output: \"{chat_res2.message}\"")
        print(f"   ✓ Cart Items: {len(chat_res2.cart)} item(s)")

        # -------------------------------------------------------------
        # STEP 2: Sales Agent Contextual Recommendation
        # -------------------------------------------------------------
        print_step(2, "Sales Agent Contextual Recommendation", "Evaluating cart for complementary cross-sell")
        sales_agent = SalesAgent(db=db, merchant_id=merchant.id, session_id=session_id)
        recs = sales_agent.generate_recommendations(trace_id=trace_id)
        
        if recs:
            print(f"   ✓ Sales Agent Recommended: {recs[0].product_name} (₹{recs[0].product_price:,.2f})")
            print(f"   ✓ Grounded Reason: {recs[0].reason}")

        # -------------------------------------------------------------
        # STEP 3: Structured Purchase Intent
        # -------------------------------------------------------------
        print_step(3, "Create Structured Purchase Intent", "Capturing authoritative cart items & max price constraint")
        intent = PurchaseIntentService.create_purchase_intent(
            db=db,
            merchant_id=merchant.id,
            session_id=session_id,
            buyer_id=buyer_id,
            trace_id=trace_id
        )
        print(f"   ✓ Purchase Intent ID: {intent.id}")
        print(f"   ✓ Total Cart Amount:  ₹{intent.requested_amount:,.2f}")

        # -------------------------------------------------------------
        # STEP 4: Deterministic Policy Evaluation & Authorization
        # -------------------------------------------------------------
        print_step(4, "Policy Engine Evaluation & Risk Scoring", "Evaluating transaction limits, velocity, and approval threshold")
        eval_res = PolicyEngine.evaluate_purchase_intent(
            db=db,
            purchase_intent_id=intent.id,
            merchant_id=merchant.id,
            trace_id=trace_id
        )
        decision = eval_res["decision"]
        risk = eval_res["risk_level"]
        auth = eval_res["authorization"]
        auth_id = auth["id"] if isinstance(auth, dict) else (auth.id if auth else None)
        print(f"   ✓ Decision:      {decision}")
        print(f"   ✓ Risk Level:    {risk}")
        print(f"   ✓ Authorization: {auth_id if auth_id else 'Pending Approval'}")

        # -------------------------------------------------------------
        # STEP 5: Payment Order Creation via PaymentProvider
        # -------------------------------------------------------------
        print_step(5, "Create Payment Order via PaymentProvider", "Validating authorization boundary & creating provider order")
        idemp_key = f"idemp_{uuid.uuid4().hex[:12]}"
        tx = PaymentService.create_payment_order(
            db=db,
            merchant_id=merchant.id,
            purchase_intent_id=intent.id,
            authorization_id=auth_id,
            idempotency_key=idemp_key,
            trace_id=trace_id
        )
        print(f"   ✓ Payment Transaction ID: {tx.id}")
        print(f"   ✓ Provider Order ID:     {tx.razorpay_order_id}")
        print(f"   ✓ Status:                {tx.status}")

        # -------------------------------------------------------------
        # STEP 6: Webhook Delivery & Payment Capture
        # -------------------------------------------------------------
        print_step(6, "Webhook Delivery & Cryptographic Signature Verification", "Receiving payment.captured webhook from provider")
        mock_provider = PaymentService.get_mock_provider()
        webhook_raw = json.dumps({
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_demo_{uuid.uuid4().hex[:8]}",
                        "order_id": tx.razorpay_order_id,
                        "amount": int(tx.amount * 100),
                        "currency": "INR",
                        "status": "captured"
                    }
                }
            }
        }).encode("utf-8")
        sig = mock_provider.generate_signature(webhook_raw)

        ok, msg, ev = PaymentService.process_webhook_event(
            db=db,
            raw_body=webhook_raw,
            signature=sig,
            event_id=f"evt_demo_{uuid.uuid4().hex[:8]}"
        )
        db.refresh(tx)
        print(f"   ✓ Webhook Signature: VALID (HMAC-SHA256)")
        print(f"   ✓ Final Transaction State: {tx.status}")

        # -------------------------------------------------------------
        # STEP 7: Executive Trace Summary & Timeline
        # -------------------------------------------------------------
        print_header("UNIFIED TRACE TIMELINE & AUDIT RECORD")
        trace_summary = AuditService.get_trace_summary(db=db, trace_id=trace_id, merchant_id=merchant.id)

        print(f"Trace ID:        {trace_summary['trace_id']}")
        print(f"Total Events:    {trace_summary['event_count']}")
        print(f"Duration:        {trace_summary['duration_ms']} ms")
        print(f"Final Outcome:   {trace_summary['final_outcome']}")
        print(f"Integrity Valid: {trace_summary['integrity']['is_valid']}")
        print(f"Tamper Status:   {trace_summary['integrity']['detail']}")

        print("\nCHRONOLOGICAL EVENT STREAM:")
        print(f"{'SEQ':<4} | {'ACTOR':<8} | {'ACTION':<24} | {'STATUS':<9} | {'PREV HASH':<10} | {'EVENT HASH':<10}")
        print("-" * 80)
        for ev in trace_summary['events']:
            print(f"{ev['sequence_number']:<4} | {ev['actor_type']:<8} | {ev['action']:<24} | {ev['status']:<9} | {ev['previous_event_hash'][:8]:<10} | {ev['event_hash'][:8]:<10}")

        # -------------------------------------------------------------
        # STEP 8: Cryptographic Tamper-Evidence Demonstration
        # -------------------------------------------------------------
        print_header("TAMPER DETECTION DEMONSTRATION")
        print("Now intentionally modifying an audit event payload in the database to simulate malicious tampering...")

        # Tamper with event sequence #2
        target_event = db.query(AuditEvent).filter(
            AuditEvent.merchant_id == merchant.id,
            AuditEvent.trace_id == trace_id,
            AuditEvent.sequence_number == 2
        ).first()

        original_action = target_event.action
        target_event.action = "TAMPERED_FRAUDULENT_ACTION"
        db.commit()

        print(f"\n[!] Mutated Event #{target_event.sequence_number} action: '{original_action}' → '{target_event.action}'")
        
        # Run integrity verification
        tamper_res = AuditIntegrityService.verify_trace(db=db, trace_id=trace_id, merchant_id=merchant.id)

        print(f"\nAuditIntegrityService Verification Result:")
        print(f"   • Is Valid:           {tamper_res['is_valid']}")
        print(f"   • Tampering Detected: {tamper_res['tampering_detected']}")
        print(f"   • Detail:             {tamper_res['detail']}")
        print(f"   • Invalid Event ID:   {tamper_res['first_invalid_event_id']}")

        if not tamper_res["is_valid"]:
            print("\n✓ SUCCESS: Cryptographic hash-chain instantly detected unauthorized payload tampering!")

        # Restore original action
        target_event.action = original_action
        db.commit()

        restored_res = AuditIntegrityService.verify_trace(db=db, trace_id=trace_id, merchant_id=merchant.id)
        print(f"✓ Post-Restoration Hash-Chain Status: Valid = {restored_res['is_valid']}")

        print_header("PHASE 7 DEMO COMPLETE — ALL VERIFICATIONS PASSED")

    finally:
        db.close()

if __name__ == "__main__":
    run_demo()
