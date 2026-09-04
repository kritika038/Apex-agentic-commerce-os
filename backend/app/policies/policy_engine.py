from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.database.models.policy import Policy
from app.database.models.policy_evaluation import PolicyEvaluation
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.cart import Cart, CartItem
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.approval_request import ApprovalRequest
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.agent import Agent
from app.policies.risk_engine import RiskEngine

class PolicyEngine:
    """
    Deterministic Financial Policy Engine.
    
    Principles:
    - 100% deterministic, containing zero LLM calls.
    - Uses exact Decimal arithmetic for all monetary evaluations.
    - Records immutable policy snapshots for reproducible audit trails.
    - Enforces least privilege agent permissions and race-safe transaction states.
    """
    @staticmethod
    def get_or_create_default_policy(db: Session, merchant_id: str) -> Policy:
        policy = db.query(Policy).filter(
            Policy.merchant_id == merchant_id,
            Policy.is_active == True
        ).order_by(Policy.version.desc()).first()
        
        if not policy:
            policy = Policy(
                merchant_id=merchant_id,
                name="Default Commerce Policy",
                version=1,
                max_transaction_amount=Decimal("10000.00"),
                approval_threshold=Decimal("5000.00"),
                low_risk_limit=Decimal("2000.00"),
                max_discount_percent=Decimal("5.00"),
                max_quantity=5,
                allowed_currency="INR",
                auto_approval_enabled=True,
                authorization_expiration_minutes=10,
                is_active=True
            )
            db.add(policy)
            db.commit()
            db.refresh(policy)
            
        return policy

    @staticmethod
    def evaluate_purchase_intent(
        db: Session,
        purchase_intent_id: str,
        merchant_id: str,
        agent_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        # 1. Retrieve authoritative PurchaseIntent
        intent = db.query(PurchaseIntent).filter(
            PurchaseIntent.id == purchase_intent_id,
            PurchaseIntent.merchant_id == merchant_id
        ).first()
        
        if not intent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase Intent '{purchase_intent_id}' not found for merchant."
            )

        # Check intent expiration
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if intent.expires_at and now > intent.expires_at:
            intent.status = "EXPIRED"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Purchase Intent has expired and cannot be evaluated."
            )

        # 2. Check for active existing authorization (Idempotency)
        existing_auth = db.query(TransactionAuthorization).filter(
            TransactionAuthorization.purchase_intent_id == intent.id,
            TransactionAuthorization.merchant_id == merchant_id,
            TransactionAuthorization.status == "AUTHORIZED",
            TransactionAuthorization.expires_at > now
        ).first()

        if existing_auth:
            latest_eval = db.query(PolicyEvaluation).filter(
                PolicyEvaluation.id == existing_auth.policy_evaluation_id
            ).first()
            if latest_eval:
                return PolicyEngine._format_evaluation_result(latest_eval, authorization=existing_auth)

        # 3. Retrieve current active merchant policy
        policy = PolicyEngine.get_or_create_default_policy(db, merchant_id)

        # 4. Perform deterministic checks
        checks: List[Dict[str, Any]] = []
        violations: List[str] = []

        # Check A: Purchase Intent Status Check
        if intent.status in ("EXPIRED", "REJECTED"):
            violations.append(f"Purchase Intent is in invalid state: '{intent.status}'")
            checks.append({"rule": "PURCHASE_INTENT_VALIDITY", "passed": False, "details": f"Status: {intent.status}"})
        else:
            checks.append({"rule": "PURCHASE_INTENT_VALIDITY", "passed": True, "details": f"Status: {intent.status}"})

        # Check B: Maximum Transaction Limit
        amount = Decimal(str(intent.requested_amount))
        if amount > policy.max_transaction_amount:
            violations.append(f"Transaction amount (₹{amount:,.2f}) exceeds maximum transaction limit (₹{policy.max_transaction_amount:,.2f}).")
            checks.append({"rule": "MAX_TRANSACTION", "passed": False, "details": f"Amount ₹{amount:,.2f} > Limit ₹{policy.max_transaction_amount:,.2f}"})
        else:
            checks.append({"rule": "MAX_TRANSACTION", "passed": True, "details": f"Amount ₹{amount:,.2f} <= Limit ₹{policy.max_transaction_amount:,.2f}"})

        # Check C: Currency Whitelist
        currency = intent.currency or "INR"
        if currency != policy.allowed_currency:
            violations.append(f"Currency '{currency}' is not allowed by policy. Required: '{policy.allowed_currency}'.")
            checks.append({"rule": "CURRENCY", "passed": False, "details": f"Currency '{currency}' != Allowed '{policy.allowed_currency}'"})
        else:
            checks.append({"rule": "CURRENCY", "passed": True, "details": f"Currency '{currency}' allowed."})

        # Check D: Total Item Quantity
        items = intent.product_summary.get("items", []) if intent.product_summary else []
        total_quantity = sum(int(it.get("quantity", 1)) for it in items)
        if total_quantity > policy.max_quantity:
            violations.append(f"Total item quantity ({total_quantity}) exceeds maximum allowed quantity ({policy.max_quantity}).")
            checks.append({"rule": "MAX_QUANTITY", "passed": False, "details": f"Quantity {total_quantity} > Limit {policy.max_quantity}"})
        else:
            checks.append({"rule": "MAX_QUANTITY", "passed": True, "details": f"Quantity {total_quantity} <= Limit {policy.max_quantity}"})

        # Check E: Inventory & Product Active Verification
        inventory_passed = True
        for it in items:
            p_id = it.get("product_id")
            req_qty = int(it.get("quantity", 1))
            prod = db.query(Product).filter(Product.id == p_id, Product.merchant_id == merchant_id).first()
            if not prod or not prod.is_active:
                inventory_passed = False
                violations.append(f"Product '{it.get('name', p_id)}' is inactive or not found.")
                break
            inv = db.query(Inventory).filter(Inventory.product_id == p_id, Inventory.merchant_id == merchant_id).first()
            if not inv or inv.stock_quantity < req_qty:
                inventory_passed = False
                violations.append(f"Insufficient stock for '{prod.name}'. Requested: {req_qty}, Available: {inv.stock_quantity if inv else 0}.")
                break
        checks.append({"rule": "INVENTORY_AVAILABLE", "passed": inventory_passed, "details": "Stock and active product verification."})

        # Check F: Agent Permissions
        agent_passed = True
        if agent_id:
            agent_record = db.query(Agent).filter(Agent.id == agent_id, Agent.merchant_id == merchant_id).first()
            if not agent_record or agent_record.status != "active":
                agent_passed = False
                violations.append(f"Agent '{agent_id}' is not active or unauthorized.")
        checks.append({"rule": "AGENT_PERMISSION", "passed": agent_passed, "details": "Agent authorization verified."})

        # 5. Deterministic Risk Evaluation
        risk_result = RiskEngine.evaluate_risk(
            amount=amount,
            quantity=total_quantity,
            policy=policy,
            violations=violations
        )
        risk_level = risk_result["risk_level"]

        # 6. Determine Decision
        if violations:
            decision = "DENY"
            requires_human_approval = False
            intent.status = "REJECTED"
        elif amount > policy.approval_threshold or not policy.auto_approval_enabled:
            decision = "REQUIRES_APPROVAL"
            requires_human_approval = True
            # Purchase intent remains in CREATED state awaiting human review
        else:
            decision = "ALLOW"
            requires_human_approval = False
            intent.status = "VALIDATED"

        # 7. Persist PolicyEvaluation with immutable snapshot
        policy_eval = PolicyEvaluation(
            merchant_id=merchant_id,
            policy_id=policy.id,
            policy_version=policy.version,
            policy_snapshot=policy.to_snapshot(),
            purchase_intent_id=intent.id,
            trace_id=trace_id or intent.trace_id,
            decision=decision,
            risk_level=risk_level,
            requires_human_approval=requires_human_approval,
            checks=checks,
            violations=violations,
            evaluated_at=now
        )
        db.add(policy_eval)
        db.flush()

        created_auth: Optional[TransactionAuthorization] = None
        created_approval: Optional[ApprovalRequest] = None

        # 8. Action based on decision
        if decision == "ALLOW":
            auth_expires = now + timedelta(minutes=policy.authorization_expiration_minutes)
            created_auth = TransactionAuthorization(
                merchant_id=merchant_id,
                purchase_intent_id=intent.id,
                policy_evaluation_id=policy_eval.id,
                policy_version=policy.version,
                status="AUTHORIZED",
                authorized_amount=amount,
                currency=currency,
                authorized_by="POLICY_ENGINE_AUTO",
                authorized_at=now,
                expires_at=auth_expires
            )
            db.add(created_auth)

        elif decision == "REQUIRES_APPROVAL":
            # Check if pending approval already exists
            existing_approval = db.query(ApprovalRequest).filter(
                ApprovalRequest.purchase_intent_id == intent.id,
                ApprovalRequest.status == "PENDING"
            ).first()

            if not existing_approval:
                appr_expires = now + timedelta(minutes=15)
                created_approval = ApprovalRequest(
                    merchant_id=merchant_id,
                    purchase_intent_id=intent.id,
                    policy_evaluation_id=policy_eval.id,
                    requested_by_agent_id=agent_id,
                    amount=amount,
                    currency=currency,
                    risk_level=risk_level,
                    status="PENDING",
                    reason=f"Transaction (₹{amount:,.2f}) exceeds automatic approval threshold (₹{policy.approval_threshold:,.2f}).",
                    expires_at=appr_expires
                )
                db.add(created_approval)
            else:
                created_approval = existing_approval

        from app.services.audit_service import AuditService
        # Record Policy Evaluation Audit Event
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=policy_eval.trace_id,
            session_id=intent.session_id,
            purchase_intent_id=intent.id,
            actor_type="SYSTEM",
            action="EVALUATE_POLICY",
            event_type="POLICY_EVALUATION",
            policy_result=decision,
            risk_level=risk_level,
            decision=decision,
            status="SUCCESS" if decision != "DENY" else "DENIED",
            reason=", ".join(violations) if violations else f"Risk level assessed as {risk_level}",
            metadata_json={
                "policy_id": policy.id,
                "policy_version": policy.version,
                "requested_amount": str(amount),
                "risk_level": risk_level,
                "checks": checks,
                "violations": violations
            }
        )

        if created_auth:
            AuditService.record_event(
                db=db,
                merchant_id=merchant_id,
                trace_id=policy_eval.trace_id,
                session_id=intent.session_id,
                purchase_intent_id=intent.id,
                authorization_id=created_auth.id,
                actor_type="SYSTEM",
                action="AUTHORIZE_TRANSACTION",
                event_type="AUTHORIZATION_CREATED",
                status="SUCCESS",
                new_state="AUTHORIZED",
                metadata_json={
                    "authorized_amount": str(amount),
                    "currency": currency,
                    "authorized_by": created_auth.authorized_by
                }
            )

        if created_approval and decision == "REQUIRES_APPROVAL":
            AuditService.record_event(
                db=db,
                merchant_id=merchant_id,
                trace_id=policy_eval.trace_id,
                session_id=intent.session_id,
                purchase_intent_id=intent.id,
                approval_request_id=created_approval.id,
                actor_type="SYSTEM",
                action="REQUIRE_APPROVAL",
                event_type="APPROVAL_REQUIRED",
                status="SUCCESS",
                risk_level=risk_level,
                reason=created_approval.reason,
                metadata_json={
                    "amount": str(amount),
                    "currency": currency,
                    "reason": created_approval.reason
                }
            )

        db.commit()
        db.refresh(policy_eval)
        if created_auth:
            db.refresh(created_auth)
        if created_approval:
            db.refresh(created_approval)

        return PolicyEngine._format_evaluation_result(
            policy_eval,
            authorization=created_auth,
            approval_request=created_approval
        )

    @staticmethod
    def _format_evaluation_result(
        policy_eval: PolicyEvaluation,
        authorization: Optional[TransactionAuthorization] = None,
        approval_request: Optional[ApprovalRequest] = None
    ) -> Dict[str, Any]:
        auth_data = None
        if authorization:
            auth_data = {
                "id": authorization.id,
                "status": authorization.status,
                "authorized_amount": str(authorization.authorized_amount),
                "currency": authorization.currency,
                "authorized_by": authorization.authorized_by,
                "authorized_at": authorization.authorized_at.isoformat() if authorization.authorized_at else None,
                "expires_at": authorization.expires_at.isoformat() if authorization.expires_at else None
            }

        appr_data = None
        if approval_request:
            appr_data = {
                "id": approval_request.id,
                "status": approval_request.status,
                "amount": str(approval_request.amount),
                "currency": approval_request.currency,
                "risk_level": approval_request.risk_level,
                "reason": approval_request.reason,
                "expires_at": approval_request.expires_at.isoformat() if approval_request.expires_at else None
            }

        return {
            "id": policy_eval.id,
            "merchant_id": policy_eval.merchant_id,
            "policy_id": policy_eval.policy_id,
            "policy_version": policy_eval.policy_version,
            "purchase_intent_id": policy_eval.purchase_intent_id,
            "trace_id": policy_eval.trace_id,
            "decision": policy_eval.decision,
            "risk_level": policy_eval.risk_level,
            "requires_human_approval": policy_eval.requires_human_approval,
            "checks": policy_eval.checks or [],
            "violations": policy_eval.violations or [],
            "policy_snapshot": policy_eval.policy_snapshot or {},
            "evaluated_at": policy_eval.evaluated_at.isoformat() if policy_eval.evaluated_at else None,
            "authorization": auth_data,
            "approval_request": appr_data
        }
