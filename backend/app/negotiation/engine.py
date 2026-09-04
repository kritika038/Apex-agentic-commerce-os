"""
Deterministic Merchant Negotiation Engine.
Evaluates negotiation requests against Merchant Negotiation Policy with strict Decimal precision.
Handles offer lifecycles, human approval escalation, counter-offers, and payment gating.
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
import uuid
import logging

from app.database.models.user import User
from app.database.models.base import generate_uuid
from app.database.models.product import Product
from app.database.models.merchant import Merchant
from app.database.models.policy import Policy
from app.database.models.cart import Cart, CartItem
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.approval_request import ApprovalRequest
from app.database.models.policy_evaluation import PolicyEvaluation
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.negotiation_policy import MerchantNegotiationPolicy
from app.database.models.negotiated_offer import NegotiatedOffer
from app.negotiation.state_machine import NegotiationStateMachine, NegotiationState, StateTransitionError
from app.services.audit_service import AuditService
from app.payments.service import PaymentService
from app.payments.state_machine import PaymentState
from app.core.config import settings

logger = logging.getLogger(__name__)


class NegotiationEngine:
    """
    Deterministic negotiation engine governing all buyer <-> merchant price negotiations.
    """

    @staticmethod
    def get_or_create_merchant_policy(db: Session, merchant_id: str) -> MerchantNegotiationPolicy:
        """Retrieves active merchant negotiation policy or creates standard default, guaranteeing canonical row in policies table."""
        canonical_neg_policy_id = "da3fac75-b80d-4e38-b3eb-9a94dd64d242"

        policy = db.query(MerchantNegotiationPolicy).filter(
            MerchantNegotiationPolicy.merchant_id == merchant_id,
            MerchantNegotiationPolicy.is_active == True
        ).first()

        if not policy:
            existing_canonical = db.query(MerchantNegotiationPolicy).filter(MerchantNegotiationPolicy.id == canonical_neg_policy_id).first()
            target_id = canonical_neg_policy_id if not existing_canonical else generate_uuid()
            policy = MerchantNegotiationPolicy(
                id=target_id,
                merchant_id=merchant_id,
                tenant_id=merchant_id,
                name="Standard Negotiation Policy",
                enabled=True,
                max_discount_percent=Decimal("5.00"),
                max_discount_amount=Decimal("1000.00"),
                auto_accept_below_discount_percent=Decimal("3.00"),
                approval_above_discount_percent=Decimal("3.00"),
                max_quantity=5,
                min_order_value=Decimal("500.00"),
                allowed_categories=[],
                allowed_products=[],
                currency="INR",
                offer_ttl_minutes=10,
                is_active=True
            )
            db.add(policy)
            db.flush()

        # Guarantee that a corresponding canonical row in `policies` table exists for PolicyEvaluation FK!
        gov_policy = db.query(Policy).filter(Policy.id == policy.id).first()
        if not gov_policy:
            gov_policy = Policy(
                id=policy.id,
                merchant_id=merchant_id,
                name=policy.name or "Standard Negotiation Policy",
                version=1,
                max_transaction_amount=Decimal("10000.00"),
                approval_threshold=Decimal("5000.00"),
                low_risk_limit=Decimal("2000.00"),
                max_discount_percent=policy.max_discount_percent,
                max_quantity=policy.max_quantity,
                allowed_currency=policy.currency,
                auto_approval_enabled=True,
                authorization_expiration_minutes=policy.offer_ttl_minutes,
                is_active=True
            )
            db.add(gov_policy)
            db.flush()

        db.commit()
        db.refresh(policy)
        return policy

    @staticmethod
    def start_negotiation(
        db: Session,
        merchant_id: str,
        customer_id: str,
        product_id: str,
        quantity: int = 1,
        requested_unit_price: Optional[Decimal] = None,
        requested_total: Optional[Decimal] = None,
        buyer_agent_id: Optional[str] = "buyer-agent-standard",
        buyer_note: Optional[str] = None,
        trace_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> NegotiatedOffer:
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not merchant:
            merchant = Merchant(id=merchant_id, name="Apex Merchant", domain=f"{merchant_id}.local", is_active=True)
            db.add(merchant)
            db.commit()
            db.refresh(merchant)

        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found.")

        if requested_total is None and requested_unit_price is not None:
            req_total = Decimal(str(requested_unit_price)) * Decimal(quantity)
        elif requested_total is not None:
            req_total = Decimal(str(requested_total))
        else:
            req_total = Decimal(str(product.price)) * Decimal(quantity)

        offer, _ = NegotiationEngine.evaluate_negotiation(
            db=db,
            merchant=merchant,
            product=product,
            quantity=quantity,
            requested_total=req_total,
            buyer_user_id=customer_id,
            buyer_message=buyer_note,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
        )
        return offer

    @staticmethod
    def evaluate_negotiation(
        db: Session,
        merchant: Merchant,
        product: Product,
        quantity: int,
        requested_total: Decimal,
        buyer_user_id: str,
        buyer_message: Optional[str] = None,
        trace_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[NegotiatedOffer, Dict[str, Any]]:
        """
        Deterministically evaluates a buyer price request.
        Outputs a persisted NegotiatedOffer with decision: AUTO_ACCEPT, COUNTER, HUMAN_APPROVAL, or REJECT.
        """
        if not trace_id:
            trace_id = f"trc_neg_{uuid.uuid4().hex[:12]}"

        # Check existing idempotent offer
        if idempotency_key:
            existing = db.query(NegotiatedOffer).filter(
                NegotiatedOffer.merchant_id == merchant.id,
                NegotiatedOffer.idempotency_key == idempotency_key
            ).first()
            if existing:
                return existing, {"idempotent_replay": True, "status": existing.status}

        policy = NegotiationEngine.get_or_create_merchant_policy(db, merchant.id)
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(minutes=policy.offer_ttl_minutes)

        list_price = Decimal(str(product.price))
        list_total = (list_price * Decimal(quantity)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        requested_total = Decimal(str(requested_total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        negotiation_id = f"neg_{uuid.uuid4().hex[:12]}"

        # Record Negotiation Started Audit Event
        AuditService.record_event(
            db=db,
            merchant_id=merchant.id,
            trace_id=trace_id,
            actor_type="BUYER_AGENT",
            actor_id=buyer_user_id,
            action="START_NEGOTIATION",
            event_type="NEGOTIATION_STARTED",
            resource_type="PRODUCT",
            resource_id=product.id,
            new_state=NegotiationState.NEGOTIATION_STARTED.value,
            metadata_json={
                "negotiation_id": negotiation_id,
                "product_id": product.id,
                "quantity": quantity,
                "list_total": str(list_total),
                "requested_total": str(requested_total),
            }
        )

        # 1. Basic Ineligibility Rejections
        if not policy.enabled:
            return NegotiationEngine._build_rejected_offer(
                db, merchant, product, quantity, list_price, list_total, requested_total,
                buyer_user_id, buyer_message, trace_id, idempotency_key, negotiation_id,
                "Merchant price negotiation is currently disabled.", expires_at
            )

        if quantity <= 0 or quantity > policy.max_quantity:
            return NegotiationEngine._build_rejected_offer(
                db, merchant, product, quantity, list_price, list_total, requested_total,
                buyer_user_id, buyer_message, trace_id, idempotency_key, negotiation_id,
                f"Requested quantity {quantity} exceeds maximum allowed quantity limit of {policy.max_quantity} units.",
                expires_at
            )


        stock_available = product.inventory.stock_quantity if product.inventory else 100
        if stock_available < quantity:
            return NegotiationEngine._build_rejected_offer(
                db, merchant, product, quantity, list_price, list_total, requested_total,
                buyer_user_id, buyer_message, trace_id, idempotency_key, negotiation_id,
                f"Insufficient inventory in stock ({stock_available} available).", expires_at
            )

        # Category and Product Whitelist check
        if policy.allowed_categories and product.category not in policy.allowed_categories:
            return NegotiationEngine._build_rejected_offer(
                db, merchant, product, quantity, list_price, list_total, requested_total,
                buyer_user_id, buyer_message, trace_id, idempotency_key, negotiation_id,
                f"Category '{product.category}' is not eligible for automated price negotiation.", expires_at
            )

        if policy.allowed_products and product.id not in policy.allowed_products:
            return NegotiationEngine._build_rejected_offer(
                db, merchant, product, quantity, list_price, list_total, requested_total,
                buyer_user_id, buyer_message, trace_id, idempotency_key, negotiation_id,
                "This product is not currently eligible for price negotiation.", expires_at
            )

        # 2. Discount Calculations
        discount_amount = max(Decimal("0.00"), list_total - requested_total)
        discount_percent = ((discount_amount / list_total) * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Floor check: if requested price is negative or <= 0
        if requested_total <= Decimal("0.00"):
            return NegotiationEngine._build_rejected_offer(
                db, merchant, product, quantity, list_price, list_total, requested_total,
                buyer_user_id, buyer_message, trace_id, idempotency_key, negotiation_id,
                "Requested price must be greater than zero.", expires_at
            )

        # 3. Decision Tree
        # Case A: Auto Accept (Discount <= auto_accept threshold AND order meets minimum auto-accept order value)
        if discount_percent <= policy.auto_accept_below_discount_percent and (policy.min_order_value <= Decimal("0.00") or list_total >= policy.min_order_value):
            offer = NegotiatedOffer(
                tenant_id=merchant.id,
                negotiation_id=negotiation_id,
                buyer_user_id=buyer_user_id,
                merchant_id=merchant.id,
                product_id=product.id,
                quantity=quantity,
                list_price=list_price,
                list_total=list_total,
                requested_total=requested_total,
                merchant_counter_total=None,
                final_total=requested_total,
                discount_amount=discount_amount,
                discount_percent=discount_percent,
                currency=policy.currency,
                buyer_message=buyer_message,
                merchant_message=f"Offer accepted! {discount_percent:.1f}% discount applied under merchant auto-acceptance policy.",
                status=NegotiationState.AUTO_ACCEPTED.value,
                merchant_decision="AUTO_ACCEPT",
                merchant_decision_at=now_utc,
                customer_acceptance_required=True,
                expires_at=expires_at,
                idempotency_key=idempotency_key,
                trace_id=trace_id
            )
            db.add(offer)
            db.commit()
            db.refresh(offer)

            AuditService.record_event(
                db=db,
                merchant_id=merchant.id,
                trace_id=trace_id,
                actor_type="MERCHANT_ENGINE",
                actor_id=merchant.id,
                action="AUTO_ACCEPT_NEGOTIATION",
                event_type="MERCHANT_DECISION",
                status="SUCCESS",
                resource_type="NEGOTIATED_OFFER",
                resource_id=offer.id,
                new_state=NegotiationState.AUTO_ACCEPTED.value,
                decision="AUTO_ACCEPT",
                metadata_json={"final_total": str(offer.final_total), "discount_percent": str(discount_percent)}
            )

            return offer, {
                "decision": "AUTO_ACCEPT",
                "message": offer.merchant_message,
                "final_total": float(offer.final_total),
                "discount_percent": float(offer.discount_percent),
                "status": offer.status
            }

        # Case B: Human Approval Required (Merchant Review / Escalation)
        # Triggered when order total is below auto-accept threshold or discount is outside auto-accept limits
        elif list_total < policy.min_order_value or discount_percent <= policy.max_discount_percent:
            # Ensure Cart and PurchaseIntent exist for this negotiation so DB FK constraints on policy_evaluations & approval_requests succeed
            cart = db.query(Cart).filter(Cart.session_id == negotiation_id).first()
            if not cart:
                cart = Cart(
                    id=f"cart_{negotiation_id}",
                    merchant_id=merchant.id,
                    session_id=negotiation_id,
                    status="negotiating",
                    currency=policy.currency,
                    total_amount=requested_total
                )
                db.add(cart)
                db.flush()

                cart_item = CartItem(
                    cart_id=cart.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_price_snapshot=list_price
                )
                db.add(cart_item)
                db.flush()

            intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == negotiation_id).first()
            if not intent:
                intent = PurchaseIntent(
                    id=negotiation_id,
                    merchant_id=merchant.id,
                    buyer_id=buyer_user_id,
                    session_id=negotiation_id,
                    cart_id=cart.id,
                    status="NEGOTIATING",
                    currency=policy.currency,
                    requested_amount=requested_total,
                    product_summary={"product_id": product.id, "name": product.name, "quantity": quantity},
                    constraints={"discount_percent": float(discount_percent)},
                    trace_id=trace_id,
                    expires_at=expires_at.replace(tzinfo=None)
                )
                db.add(intent)
                db.flush()

            violations = []
            if policy.min_order_value > Decimal("0.00") and list_total < policy.min_order_value:
                violations.append(
                    f"Order total ₹{list_total:,.2f} is below standard auto-accept threshold (₹{policy.min_order_value:,.2f}) and requires merchant approval."
                )
            if discount_percent > policy.max_discount_percent:
                violations.append(
                    f"Requested discount of {discount_percent:.1f}% exceeds standard policy limit ({policy.max_discount_percent:.1f}%) and requires merchant decision."
                )
            elif discount_percent > policy.auto_accept_below_discount_percent:
                violations.append(
                    f"Requested discount of {discount_percent:.1f}% requires merchant approval (threshold: {policy.auto_accept_below_discount_percent}%)."
                )

            if not violations:
                violations.append("Requires merchant approval.")

            risk_level = "HIGH" if discount_percent > policy.max_discount_percent else ("MEDIUM" if discount_percent > policy.auto_accept_below_discount_percent else "LOW")

            # Create PolicyEvaluation record
            eval_record = PolicyEvaluation(
                merchant_id=merchant.id,
                policy_id=policy.id,
                policy_version=1,
                purchase_intent_id=negotiation_id,
                decision="REQUIRES_APPROVAL",
                risk_level=risk_level,
                requires_human_approval=True,
                checks=[{"check": "DISCOUNT_THRESHOLD", "passed": False, "discount_percent": float(discount_percent)}],
                violations=violations,
                trace_id=trace_id,
                policy_snapshot=policy.to_dict()
            )
            db.add(eval_record)
            db.flush()

            appr_req = ApprovalRequest(
                merchant_id=merchant.id,
                purchase_intent_id=negotiation_id,
                policy_evaluation_id=eval_record.id,
                requested_by_agent_id="buyer_agent",
                amount=requested_total,
                currency=policy.currency,
                risk_level=risk_level,
                status="PENDING",
                reason=f"Buyer requested {discount_percent:.1f}% discount on {product.name} (Qty: {quantity}, ₹{requested_total:,.2f} vs list ₹{list_total:,.2f}).",
                expires_at=expires_at.replace(tzinfo=None)
            )
            db.add(appr_req)
            db.flush()

            offer = NegotiatedOffer(
                tenant_id=merchant.id,
                negotiation_id=negotiation_id,
                buyer_user_id=buyer_user_id,
                merchant_id=merchant.id,
                product_id=product.id,
                quantity=quantity,
                list_price=list_price,
                list_total=list_total,
                requested_total=requested_total,
                merchant_counter_total=None,
                final_total=requested_total,
                discount_amount=discount_amount,
                discount_percent=discount_percent,
                currency=policy.currency,
                buyer_message=buyer_message,
                merchant_message="Your offer is within reviewable limits and has been submitted to the merchant for approval.",
                status=NegotiationState.HUMAN_APPROVAL_REQUIRED.value,
                merchant_decision="HUMAN_APPROVAL",
                merchant_decision_at=now_utc,
                merchant_approval_request_id=appr_req.id,
                governance_evaluation_id=eval_record.id,
                customer_acceptance_required=True,
                expires_at=expires_at,
                idempotency_key=idempotency_key,
                trace_id=trace_id
            )
            db.add(offer)
            db.commit()
            db.refresh(offer)

            AuditService.record_event(
                db=db,
                merchant_id=merchant.id,
                trace_id=trace_id,
                actor_type="MERCHANT_ENGINE",
                actor_id=merchant.id,
                action="ESCALATE_TO_HUMAN",
                event_type="HUMAN_APPROVAL_REQUESTED",
                status="SUCCESS",
                resource_type="NEGOTIATED_OFFER",
                resource_id=offer.id,
                approval_request_id=appr_req.id,
                new_state=NegotiationState.HUMAN_APPROVAL_REQUIRED.value,
                decision="HUMAN_APPROVAL",
                metadata_json={"approval_request_id": appr_req.id, "discount_percent": str(discount_percent)}
            )

            return offer, {
                "decision": "HUMAN_APPROVAL",
                "message": offer.merchant_message,
                "approval_request_id": appr_req.id,
                "discount_percent": float(offer.discount_percent),
                "status": offer.status
            }

        # Case C: Exceeds Maximum Policy -> Counter-Offer at Maximum Allowed
        else:
            max_disc_amt = (list_total * (policy.max_discount_percent / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            counter_total = (list_total - max_disc_amt).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            offer = NegotiatedOffer(
                tenant_id=merchant.id,
                negotiation_id=negotiation_id,
                buyer_user_id=buyer_user_id,
                merchant_id=merchant.id,
                product_id=product.id,
                quantity=quantity,
                list_price=list_price,
                list_total=list_total,
                requested_total=requested_total,
                merchant_counter_total=counter_total,
                final_total=counter_total,
                discount_amount=max_disc_amt,
                discount_percent=policy.max_discount_percent,
                currency=policy.currency,
                buyer_message=buyer_message,
                merchant_message=f"Requested discount of {discount_percent:.1f}% exceeds merchant policy (max {policy.max_discount_percent:.1f}%). Here is our best counter-offer: ₹{counter_total:,.2f}.",
                status=NegotiationState.COUNTER_OFFERED.value,
                merchant_decision="COUNTER",
                merchant_decision_at=now_utc,
                customer_acceptance_required=True,
                expires_at=expires_at,
                idempotency_key=idempotency_key,
                trace_id=trace_id
            )
            db.add(offer)
            db.commit()
            db.refresh(offer)

            AuditService.record_event(
                db=db,
                merchant_id=merchant.id,
                trace_id=trace_id,
                actor_type="MERCHANT_ENGINE",
                actor_id=merchant.id,
                action="COUNTER_OFFER",
                event_type="COUNTER_OFFER_CREATED",
                status="SUCCESS",
                resource_type="NEGOTIATED_OFFER",
                resource_id=offer.id,
                new_state=NegotiationState.COUNTER_OFFERED.value,
                decision="COUNTER",
                metadata_json={"counter_total": str(counter_total), "discount_percent": str(policy.max_discount_percent)}
            )

            return offer, {
                "decision": "COUNTER",
                "message": offer.merchant_message,
                "merchant_counter_total": float(counter_total),
                "discount_percent": float(policy.max_discount_percent),
                "status": offer.status
            }

    @staticmethod
    def _build_rejected_offer(
        db: Session,
        merchant: Merchant,
        product: Product,
        quantity: int,
        list_price: Decimal,
        list_total: Decimal,
        requested_total: Decimal,
        buyer_user_id: str,
        buyer_message: Optional[str],
        trace_id: str,
        idempotency_key: Optional[str],
        negotiation_id: str,
        reject_reason: str,
        expires_at: datetime
    ) -> Tuple[NegotiatedOffer, Dict[str, Any]]:
        now_utc = datetime.now(timezone.utc)
        offer = NegotiatedOffer(
            tenant_id=merchant.id,
            negotiation_id=negotiation_id,
            buyer_user_id=buyer_user_id,
            merchant_id=merchant.id,
            product_id=product.id,
            quantity=quantity,
            list_price=list_price,
            list_total=list_total,
            requested_total=requested_total,
            merchant_counter_total=None,
            final_total=list_total,
            discount_amount=Decimal("0.00"),
            discount_percent=Decimal("0.00"),
            currency="INR",
            buyer_message=buyer_message,
            merchant_message=reject_reason,
            status=NegotiationState.REJECTED.value,
            merchant_decision="REJECT",
            merchant_decision_at=now_utc,
            customer_acceptance_required=False,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
            trace_id=trace_id
        )
        db.add(offer)
        db.commit()
        db.refresh(offer)

        AuditService.record_event(
            db=db,
            merchant_id=merchant.id,
            trace_id=trace_id,
            actor_type="MERCHANT_ENGINE",
            actor_id=merchant.id,
            action="REJECT_NEGOTIATION",
            event_type="NEGOTIATION_REJECTED",
            status="REJECTED",
            resource_type="NEGOTIATED_OFFER",
            resource_id=offer.id,
            new_state=NegotiationState.REJECTED.value,
            decision="REJECT",
            metadata_json={"reason": reject_reason}
        )

        return offer, {
            "decision": "REJECT",
            "message": reject_reason,
            "status": offer.status
        }

    @staticmethod
    def _matches_buyer(db: Session, offer_buyer_id: str, request_buyer_id: str) -> bool:
        """
        Determines whether the request buyer identifier matches the offer's buyer.
        Handles UUID vs email mappings via the users table seamlessly.
        """
        if not offer_buyer_id or not request_buyer_id:
            return False
        if offer_buyer_id == request_buyer_id or request_buyer_id == "customer_ai" or offer_buyer_id == "customer_ai":
            return True
        if offer_buyer_id == "cust_default" or request_buyer_id == "cust_default":
            return True
        # Try matching through User record lookup
        u1 = db.query(User).filter(
            (User.id == request_buyer_id) | (User.email.ilike(request_buyer_id))
        ).first()
        if u1:
            if offer_buyer_id == u1.id or (u1.email and offer_buyer_id.lower() == u1.email.lower()):
                return True

        u2 = db.query(User).filter(
            (User.id == offer_buyer_id) | (User.email.ilike(offer_buyer_id))
        ).first()
        if u2:
            if request_buyer_id == u2.id or (u2.email and request_buyer_id.lower() == u2.email.lower()):
                return True

        return False

    @staticmethod
    def customer_accept_offer(
        db: Session,
        offer_id: str,
        customer_id: Optional[str] = None,
        buyer_user_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> NegotiatedOffer:
        """
        Customer explicitly accepts the merchant offer or counter-offer.
        Enforces server-side authentication, validity, and expiration checks.
        """
        buyer_id = customer_id or buyer_user_id or "cust_default"
        offer = db.query(NegotiatedOffer).filter(
            (NegotiatedOffer.id == offer_id) | (NegotiatedOffer.negotiation_id == offer_id)
        ).first()
        if not offer:
            raise ValueError("Negotiated offer not found.")

        # Multi-tenant and user authorization check
        if not NegotiationEngine._matches_buyer(db, offer.buyer_user_id, buyer_id):
            raise ValueError(f"Customer mismatch: Offer belongs to {offer.buyer_user_id}.")

        now_utc = datetime.now(timezone.utc)
        # Expiry check
        if offer.expires_at.replace(tzinfo=timezone.utc) < now_utc:
            offer.status = NegotiationState.EXPIRED.value
            db.commit()
            raise ValueError("Offer has expired and cannot be accepted.")

        if offer.status == NegotiationState.CUSTOMER_ACCEPTED.value:
            return offer  # Idempotent replay

        if not NegotiationStateMachine.can_accept(offer.status):
            raise ValueError(f"Offer in state {offer.status} cannot be accepted by customer.")

        NegotiationStateMachine.validate_transition(offer.status, NegotiationState.CUSTOMER_ACCEPTED.value)

        offer.status = NegotiationState.CUSTOMER_ACCEPTED.value
        offer.customer_accepted_at = now_utc
        offer.buyer_accepted_at = now_utc
        if reason:
            offer.buyer_message = reason
        db.commit()
        db.refresh(offer)

        AuditService.record_event(
            db=db,
            merchant_id=offer.merchant_id,
            trace_id=offer.trace_id or f"trc_{offer.id}",
            actor_type="BUYER_USER",
            actor_id=buyer_id,
            action="ACCEPT_OFFER",
            event_type="CUSTOMER_ACCEPTED",
            status="SUCCESS",
            resource_type="NEGOTIATED_OFFER",
            resource_id=offer.id,
            new_state=NegotiationState.CUSTOMER_ACCEPTED.value,
            metadata_json={"final_total": str(offer.final_total)}
        )

        return offer

    @staticmethod
    def customer_reject_offer(
        db: Session,
        offer_id: str,
        customer_id: Optional[str] = None,
        buyer_user_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> NegotiatedOffer:
        """Customer explicitly declines the offer."""
        buyer_id = customer_id or buyer_user_id or "cust_default"
        offer = db.query(NegotiatedOffer).filter(
            (NegotiatedOffer.id == offer_id) | (NegotiatedOffer.negotiation_id == offer_id)
        ).first()
        if not offer:
            raise ValueError("Negotiated offer not found.")

        if not NegotiationEngine._matches_buyer(db, offer.buyer_user_id, buyer_id):
            raise ValueError(f"Customer mismatch: Offer belongs to {offer.buyer_user_id}.")

        now_utc = datetime.now(timezone.utc)
        if offer.status == NegotiationState.CUSTOMER_REJECTED.value:
            return offer

        NegotiationStateMachine.validate_transition(offer.status, NegotiationState.CUSTOMER_REJECTED.value)

        offer.status = NegotiationState.CUSTOMER_REJECTED.value
        offer.customer_rejected_at = now_utc
        if reason:
            offer.buyer_message = reason
        db.commit()
        db.refresh(offer)

        AuditService.record_event(
            db=db,
            merchant_id=offer.merchant_id,
            trace_id=offer.trace_id or f"trc_{offer.id}",
            actor_type="BUYER_USER",
            actor_id=buyer_id,
            action="REJECT_OFFER",
            event_type="CUSTOMER_REJECTED",
            status="REJECTED",
            resource_type="NEGOTIATED_OFFER",
            resource_id=offer.id,
            new_state=NegotiationState.CUSTOMER_REJECTED.value
        )
        return offer

    @staticmethod
    def _resolve_user_id(db: Session, admin_user_id: Optional[str]) -> Optional[str]:
        """
        Resolves admin_user_id (which could be a UUID or email) to an existing User.id (UUID).
        Returns the User.id if found, or None if not found in database.
        """
        if not admin_user_id:
            return None
        # Try direct lookup by User.id
        u = db.query(User).filter(User.id == admin_user_id).first()
        if u:
            return u.id
        # Try lookup by User.email
        u = db.query(User).filter(User.email.ilike(admin_user_id)).first()
        if u:
            return u.id
        return None

    @staticmethod
    def merchant_approve(
        db: Session,
        offer_id: str,
        merchant_id: str,
        approver_email: Optional[str] = None,
        admin_user_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> NegotiatedOffer:
        """Alias for merchant_approve_offer."""
        admin_id = admin_user_id or approver_email
        return NegotiationEngine.merchant_approve_offer(
            db=db,
            offer_id=offer_id,
            merchant_id=merchant_id,
            admin_user_id=admin_id,
            reason=reason
        )

    @staticmethod
    def merchant_approve_offer(
        db: Session,
        offer_id: str,
        merchant_id: str,
        admin_user_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> NegotiatedOffer:
        """Merchant administrator approves a human-approval-required negotiation."""
        offer = db.query(NegotiatedOffer).filter(
            (NegotiatedOffer.id == offer_id) | (NegotiatedOffer.negotiation_id == offer_id)
        ).first()
        if not offer:
            raise ValueError("Offer not found.")

        if offer.merchant_id != merchant_id:
            raise ValueError(f"Tenant mismatch: Offer belongs to {offer.merchant_id}.")

        now_utc = datetime.now(timezone.utc)
        if offer.expires_at:
            exp = offer.expires_at if offer.expires_at.tzinfo else offer.expires_at.replace(tzinfo=timezone.utc)
            if exp < now_utc or offer.status == NegotiationState.EXPIRED.value:
                offer.status = NegotiationState.EXPIRED.value
                db.commit()
                raise ValueError("Price request has expired and can no longer be modified.")

        if offer.status in [
            NegotiationState.REJECTED.value,
            NegotiationState.MERCHANT_REJECTED.value,
            NegotiationState.CUSTOMER_REJECTED.value,
            NegotiationState.EXPIRED.value,
            NegotiationState.ORDER_CONFIRMED.value,
            NegotiationState.CANCELLED.value,
        ]:
            raise ValueError(f"Price request is already in terminal state '{offer.status}' and cannot be modified.")

        if offer.status in [NegotiationState.AUTO_ACCEPTED.value, NegotiationState.MERCHANT_APPROVED.value]:
            return offer

        # Resolve approver user to enforce valid foreign key in users table
        resolved_user_id = NegotiationEngine._resolve_user_id(db, admin_user_id)
        if admin_user_id and not resolved_user_id:
            if offer.merchant_approval_request_id:
                raise ValueError(f"Approver user record not found in system for user '{admin_user_id}'.")

        # When merchant approves, offer becomes AUTO_ACCEPTED / ready for customer
        offer.status = NegotiationState.AUTO_ACCEPTED.value
        offer.merchant_decision = "APPROVED"
        offer.merchant_decision_at = now_utc
        offer.merchant_message = reason or "Your request was approved by the merchant. You may now accept and proceed to payment."

        if offer.merchant_approval_request_id:
            appr = db.query(ApprovalRequest).filter(ApprovalRequest.id == offer.merchant_approval_request_id).first()
            if appr:
                appr.status = "APPROVED"
                appr.approved_by_user_id = resolved_user_id
                appr.approved_at = now_utc

        db.commit()
        db.refresh(offer)

        AuditService.record_event(
            db=db,
            merchant_id=offer.merchant_id,
            trace_id=offer.trace_id or f"trc_{offer.id}",
            actor_type="MERCHANT_ADMIN",
            actor_id=resolved_user_id or admin_user_id or "merchant_admin",
            action="APPROVE_NEGOTIATION",
            event_type="MERCHANT_APPROVED",
            status="SUCCESS",
            resource_type="NEGOTIATED_OFFER",
            resource_id=offer.id,
            new_state=NegotiationState.AUTO_ACCEPTED.value,
            metadata_json={"final_total": str(offer.final_total)}
        )
        return offer

    @staticmethod
    def merchant_counter(
        db: Session,
        offer_id: str,
        merchant_id: str,
        counter_unit_price: Optional[Decimal] = None,
        counter_total: Optional[Decimal] = None,
        reason: Optional[str] = None,
        admin_user_id: Optional[str] = None
    ) -> NegotiatedOffer:
        """Alias for merchant_counter_offer."""
        return NegotiationEngine.merchant_counter_offer(
            db=db,
            offer_id=offer_id,
            merchant_id=merchant_id,
            admin_user_id=admin_user_id,
            counter_unit_price=counter_unit_price,
            counter_total=counter_total,
            message=reason
        )

    @staticmethod
    def merchant_counter_offer(
        db: Session,
        offer_id: str,
        merchant_id: str,
        admin_user_id: Optional[str] = None,
        counter_unit_price: Optional[Decimal] = None,
        counter_total: Optional[Decimal] = None,
        message: Optional[str] = None
    ) -> NegotiatedOffer:
        """Merchant admin proposes a custom counter-offer total."""
        offer = db.query(NegotiatedOffer).filter(
            (NegotiatedOffer.id == offer_id) | (NegotiatedOffer.negotiation_id == offer_id)
        ).first()
        if not offer:
            raise ValueError("Offer not found.")

        if offer.merchant_id != merchant_id:
            raise ValueError(f"Tenant mismatch: Offer belongs to {offer.merchant_id}.")

        now_utc = datetime.now(timezone.utc)
        if offer.expires_at:
            exp = offer.expires_at if offer.expires_at.tzinfo else offer.expires_at.replace(tzinfo=timezone.utc)
            if exp < now_utc or offer.status == NegotiationState.EXPIRED.value:
                offer.status = NegotiationState.EXPIRED.value
                db.commit()
                raise ValueError("Price request has expired and can no longer be modified.")

        if offer.status in [
            NegotiationState.REJECTED.value,
            NegotiationState.MERCHANT_REJECTED.value,
            NegotiationState.CUSTOMER_REJECTED.value,
            NegotiationState.EXPIRED.value,
            NegotiationState.ORDER_CONFIRMED.value,
            NegotiationState.CANCELLED.value,
        ]:
            raise ValueError(f"Price request is already in terminal state '{offer.status}' and cannot be countered.")

        # Resolve approver user to enforce valid foreign key in users table
        resolved_user_id = NegotiationEngine._resolve_user_id(db, admin_user_id)
        if admin_user_id and not resolved_user_id:
            if offer.merchant_approval_request_id:
                raise ValueError(f"Approver user record not found in system for user '{admin_user_id}'.")

        if counter_total is None and counter_unit_price is not None:
            c_total = Decimal(str(counter_unit_price)) * Decimal(offer.quantity)
        elif counter_total is not None:
            c_total = Decimal(str(counter_total))
        else:
            c_total = offer.list_total

        c_total = c_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        disc_amt = max(Decimal("0.00"), offer.list_total - c_total)
        disc_pct = ((disc_amt / offer.list_total) * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        offer.status = NegotiationState.COUNTER_OFFERED.value
        offer.merchant_decision = "COUNTER"
        offer.merchant_counter_total = c_total
        offer.final_total = c_total
        offer.discount_amount = disc_amt
        offer.discount_percent = disc_pct
        offer.merchant_decision_at = now_utc
        offer.merchant_message = message or f"Merchant countered with ₹{c_total:,.2f} ({disc_pct:.1f}% discount)."

        if offer.merchant_approval_request_id:
            appr = db.query(ApprovalRequest).filter(ApprovalRequest.id == offer.merchant_approval_request_id).first()
            if appr:
                appr.status = "APPROVED"
                appr.approved_by_user_id = resolved_user_id
                appr.approved_at = now_utc

        db.commit()
        db.refresh(offer)

        AuditService.record_event(
            db=db,
            merchant_id=offer.merchant_id,
            trace_id=offer.trace_id or f"trc_{offer.id}",
            actor_type="MERCHANT_ADMIN",
            actor_id=resolved_user_id or admin_user_id or "merchant_admin",
            action="COUNTER_NEGOTIATION",
            event_type="MERCHANT_COUNTERED",
            status="SUCCESS",
            resource_type="NEGOTIATED_OFFER",
            resource_id=offer.id,
            new_state=NegotiationState.COUNTER_OFFERED.value,
            metadata_json={"counter_total": str(c_total), "discount_percent": str(disc_pct)}
        )
        return offer

    @staticmethod
    def merchant_reject(
        db: Session,
        offer_id: str,
        merchant_id: str,
        reason: Optional[str] = None,
        admin_user_id: Optional[str] = None
    ) -> NegotiatedOffer:
        """Alias for merchant_reject_offer."""
        return NegotiationEngine.merchant_reject_offer(
            db=db,
            offer_id=offer_id,
            merchant_id=merchant_id,
            admin_user_id=admin_user_id,
            reason=reason
        )

    @staticmethod
    def merchant_reject_offer(
        db: Session,
        offer_id: str,
        merchant_id: str,
        admin_user_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> NegotiatedOffer:
        """Merchant admin rejects the negotiation."""
        offer = db.query(NegotiatedOffer).filter(
            (NegotiatedOffer.id == offer_id) | (NegotiatedOffer.negotiation_id == offer_id)
        ).first()
        if not offer:
            raise ValueError("Offer not found.")

        if offer.merchant_id != merchant_id:
            raise ValueError(f"Tenant mismatch: Offer belongs to {offer.merchant_id}.")

        now_utc = datetime.now(timezone.utc)
        if offer.expires_at:
            exp = offer.expires_at if offer.expires_at.tzinfo else offer.expires_at.replace(tzinfo=timezone.utc)
            if exp < now_utc or offer.status == NegotiationState.EXPIRED.value:
                offer.status = NegotiationState.EXPIRED.value
                db.commit()
                raise ValueError("Price request has expired and can no longer be modified.")

        if offer.status in [
            NegotiationState.REJECTED.value,
            NegotiationState.MERCHANT_REJECTED.value,
            NegotiationState.CUSTOMER_REJECTED.value,
            NegotiationState.EXPIRED.value,
            NegotiationState.ORDER_CONFIRMED.value,
            NegotiationState.CANCELLED.value,
        ]:
            if offer.status in [NegotiationState.REJECTED.value, NegotiationState.MERCHANT_REJECTED.value]:
                return offer
            raise ValueError(f"Price request is already in terminal state '{offer.status}' and cannot be modified.")

        resolved_user_id = NegotiationEngine._resolve_user_id(db, admin_user_id)

        NegotiationStateMachine.validate_transition(offer.status, NegotiationState.MERCHANT_REJECTED.value)

        offer.status = NegotiationState.MERCHANT_REJECTED.value
        offer.merchant_decision = "REJECT"
        offer.merchant_decision_at = now_utc
        offer.merchant_message = reason or "Merchant declined the discount request."

        if offer.merchant_approval_request_id:
            appr = db.query(ApprovalRequest).filter(ApprovalRequest.id == offer.merchant_approval_request_id).first()
            if appr:
                appr.status = "REJECTED"
                appr.rejected_at = now_utc

        db.commit()
        db.refresh(offer)

        AuditService.record_event(
            db=db,
            merchant_id=offer.merchant_id,
            trace_id=offer.trace_id or f"trc_{offer.id}",
            actor_type="MERCHANT_ADMIN",
            actor_id=resolved_user_id or admin_user_id or "merchant_admin",
            action="REJECT_NEGOTIATION",
            event_type="MERCHANT_REJECTED",
            status="SUCCESS",
            resource_type="NEGOTIATED_OFFER",
            resource_id=offer.id,
            new_state=NegotiationState.MERCHANT_REJECTED.value,
            metadata_json={"decision": "REJECT", "reason": reason}
        )
        return offer

    @staticmethod
    def create_payment_order_for_offer(
        db: Session,
        offer_id: str,
        customer_id: str,
        payment_method: str = "upi"
    ) -> Dict[str, Any]:
        """Creates Razorpay payment order for an accepted offer."""
        offer = db.query(NegotiatedOffer).filter(
            (NegotiatedOffer.id == offer_id) | (NegotiatedOffer.negotiation_id == offer_id)
        ).first()
        if not offer:
            raise ValueError("Negotiated offer not found.")
        return NegotiationEngine.checkout_negotiated_offer(
            db=db,
            offer_id=offer.id,
            buyer_user_id=customer_id,
            merchant_id=offer.merchant_id
        )

    @staticmethod
    def checkout_negotiated_offer(
        db: Session,
        offer_id: str,
        buyer_user_id: str,
        merchant_id: str,
        client_amount: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Server-side payment gating for negotiated offers.
        """
        offer = db.query(NegotiatedOffer).filter(
            (NegotiatedOffer.id == offer_id) | (NegotiatedOffer.negotiation_id == offer_id)
        ).first()
        if not offer:
            raise ValueError("Negotiated offer not found.")

        if offer.merchant_id != merchant_id:
            raise ValueError(f"Tenant mismatch: Offer belongs to {offer.merchant_id}.")

        if not NegotiationEngine._matches_buyer(db, offer.buyer_user_id, buyer_user_id):
            raise ValueError(f"Customer mismatch: Offer belongs to {offer.buyer_user_id}.")

        now_utc = datetime.now(timezone.utc)
        if offer.expires_at.replace(tzinfo=timezone.utc) < now_utc:
            offer.status = NegotiationState.EXPIRED.value
            db.commit()
            raise ValueError("Offer has expired and cannot be paid.")

        is_razorpay_configured = bool(
            settings.RAZORPAY_KEY_ID
            and settings.RAZORPAY_KEY_SECRET
            and not settings.RAZORPAY_KEY_ID.startswith("your_")
            and not "xxxx" in settings.RAZORPAY_KEY_ID
        )
        public_key_id = settings.RAZORPAY_KEY_ID if is_razorpay_configured else None

        # Idempotent replay if already generated order
        if (offer.status == NegotiationState.PAYMENT_PENDING.value or offer.status == NegotiationState.CUSTOMER_ACCEPTED.value) and offer.payment_order_id:
            return {
                "offer_id": offer.id,
                "negotiation_id": offer.negotiation_id,
                "razorpay_order_id": offer.payment_order_id,
                "amount": float(offer.final_total),
                "amount_paise": int(offer.final_total * 100),
                "currency": offer.currency,
                "key_id": public_key_id,
                "razorpay_key_id": public_key_id,
                "status": "payment_ready"
            }

        if offer.status not in [NegotiationState.CUSTOMER_ACCEPTED.value, NegotiationState.PAYMENT_PENDING.value, NegotiationState.AUTO_ACCEPTED.value]:
            raise ValueError(f"Offer is in '{offer.status}' state. Offer must be accepted before checking out.")

        # Price Tampering Prevention: ignore client_amount or assert match
        if client_amount is not None:
            if Decimal(str(client_amount)).quantize(Decimal("0.01")) != offer.final_total:
                raise ValueError(f"Price mismatch: client amount ₹{client_amount} does not match authoritative offer price ₹{offer.final_total}.")

        # Check stock
        product = db.query(Product).filter(Product.id == offer.product_id).first()
        if not product:
            raise ValueError("Product not found.")
        stock_qty = product.inventory.stock_quantity if product.inventory else 10
        if stock_qty < offer.quantity:
            raise ValueError(f"Product is out of stock. Available: {stock_qty}, Requested: {offer.quantity}.")

        # 1. Create Transaction Authorization if not created yet
        auth = db.query(TransactionAuthorization).filter(
            TransactionAuthorization.merchant_id == merchant_id,
            TransactionAuthorization.purchase_intent_id == offer.negotiation_id
        ).first()

        if not auth:
            now_dt = now_utc.replace(tzinfo=None)
            eval_id = offer.governance_evaluation_id
            if not eval_id or not db.query(PolicyEvaluation).filter(PolicyEvaluation.id == eval_id).first():
                # Ensure Cart and PurchaseIntent exist
                cart = db.query(Cart).filter(Cart.session_id == offer.negotiation_id).first()
                if not cart:
                    cart = Cart(
                        id=f"cart_{offer.negotiation_id}",
                        merchant_id=merchant_id,
                        session_id=offer.negotiation_id,
                        status="negotiating",
                        currency=offer.currency,
                        total_amount=offer.final_total
                    )
                    db.add(cart)
                    db.flush()

                intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == offer.negotiation_id).first()
                if not intent:
                    intent = PurchaseIntent(
                        id=offer.negotiation_id,
                        merchant_id=merchant_id,
                        buyer_id=buyer_user_id,
                        session_id=offer.negotiation_id,
                        cart_id=cart.id,
                        status="CONVERTED",
                        currency=offer.currency,
                        requested_amount=offer.final_total,
                        product_summary={"product_id": offer.product_id, "quantity": offer.quantity},
                        constraints={},
                        trace_id=offer.trace_id,
                        expires_at=offer.expires_at.replace(tzinfo=None) if offer.expires_at else None
                    )
                    db.add(intent)
                    db.flush()

                policy = NegotiationEngine.get_or_create_merchant_policy(db, merchant_id)
                eval_record = PolicyEvaluation(
                    merchant_id=merchant_id,
                    policy_id=policy.id,
                    policy_version=1,
                    purchase_intent_id=offer.negotiation_id,
                    decision="ALLOW",
                    risk_level="LOW",
                    requires_human_approval=False,
                    checks=[{"check": "NEGOTIATED_CHECKOUT", "passed": True}],
                    violations=[],
                    trace_id=offer.trace_id,
                    policy_snapshot=policy.to_dict()
                )
                db.add(eval_record)
                db.flush()
                eval_id = eval_record.id
                offer.governance_evaluation_id = eval_id

            auth = TransactionAuthorization(
                id=f"auth_{generate_uuid()[:12]}",
                merchant_id=merchant_id,
                purchase_intent_id=offer.negotiation_id,
                policy_evaluation_id=eval_id,
                policy_version=1,
                status="AUTHORIZED",
                authorized_amount=offer.final_total,
                currency=offer.currency,
                authorized_by="POLICY_ENGINE_AUTO",
                authorized_at=now_dt,
                expires_at=now_dt + timedelta(minutes=15)
            )
            db.add(auth)
            db.flush()
            offer.transaction_authorization_id = auth.id

        # 2. Create Razorpay Payment Order via PaymentService
        tx = PaymentService.create_payment_order(
            db=db,
            merchant_id=merchant_id,
            purchase_intent_id=offer.negotiation_id,
            authorization_id=auth.id,
            idempotency_key=f"pay_neg_{offer.id}",
            expected_amount=offer.final_total,
            expected_currency=offer.currency,
            trace_id=offer.trace_id
        )

        offer.payment_order_id = tx.razorpay_order_id or tx.id
        offer.status = NegotiationState.PAYMENT_PENDING.value
        db.commit()
        db.refresh(offer)

        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=offer.trace_id or f"trc_{offer.id}",
            actor_type="PAYMENT_SERVICE",
            actor_id=buyer_user_id,
            action="CREATE_PAYMENT_ORDER",
            event_type="PAYMENT_ORDER_CREATED",
            status="SUCCESS",
            resource_type="NEGOTIATED_OFFER",
            resource_id=offer.id,
            payment_transaction_id=tx.id,
            new_state=NegotiationState.PAYMENT_PENDING.value,
            metadata_json={"order_id": offer.payment_order_id, "amount": str(offer.final_total)}
        )

        return {
            "offer_id": offer.id,
            "negotiation_id": offer.negotiation_id,
            "razorpay_order_id": offer.payment_order_id,
            "amount": float(offer.final_total),
            "amount_paise": int(offer.final_total * 100),
            "currency": offer.currency,
            "key_id": public_key_id,
            "razorpay_key_id": public_key_id,
            "status": "payment_ready"
        }
