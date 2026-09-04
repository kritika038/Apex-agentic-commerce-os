"""
Merchant Negotiation Agent.
Coordinates buyer <-> merchant agent negotiation requests, invokes deterministic NegotiationEngine,
and provides auditable agent traces and conversational rationales.
"""

from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import logging

from app.negotiation.engine import NegotiationEngine
from app.negotiation.state_machine import NegotiationState
from app.database.models.negotiated_offer import NegotiatedOffer
from app.database.models.product import Product

logger = logging.getLogger(__name__)


class MerchantNegotiationAgent:
    """
    AI Merchant Negotiation Agent.
    Operates under strict merchant policy bounds with deterministic governance.
    """

    def __init__(self, db: Session, merchant_id: str = "merch_default"):
        self.db = db
        self.merchant_id = merchant_id
        self.engine = NegotiationEngine()

    def process_buyer_negotiation_request(
        self,
        product_id: str,
        quantity: int,
        requested_unit_price: Optional[Decimal] = None,
        requested_total: Optional[Decimal] = None,
        customer_id: str = "cust_default",
        buyer_agent_id: str = "buyer-agent-standard",
        buyer_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes an incoming buyer agent negotiation proposal.
        """
        logger.info(
            f"MerchantNegotiationAgent processing proposal for product {product_id}, qty {quantity}, customer {customer_id}"
        )

        offer = self.engine.start_negotiation(
            db=self.db,
            merchant_id=self.merchant_id,
            customer_id=customer_id,
            product_id=product_id,
            quantity=quantity,
            requested_unit_price=requested_unit_price,
            requested_total=requested_total,
            buyer_agent_id=buyer_agent_id,
            buyer_note=buyer_note
        )

        # Generate agent response summary
        agent_message = self._generate_agent_response(offer)

        return {
            "offer": offer,
            "agent_message": agent_message,
            "status": offer.status,
            "requires_action": (
                "MERCHANT" if offer.status == NegotiationState.HUMAN_APPROVAL_REQUIRED.value
                else "CUSTOMER" if offer.status in [NegotiationState.AUTO_ACCEPTED.value, NegotiationState.COUNTER_OFFERED.value]
                else "NONE"
            ),
            "trace": {
                "buyer_agent_id": buyer_agent_id,
                "merchant_agent_id": f"merchant-agent-{self.merchant_id}",
                "rule_evaluation": offer.metadata_json.get("policy_evaluation", {}) if offer.metadata_json else {},
                "audit_hash": offer.audit_hash
            }
        }

    def _generate_agent_response(self, offer: NegotiatedOffer) -> str:
        """Generates clear, contextual business rationale for the buyer agent / customer."""
        prod = self.db.query(Product).filter(Product.id == offer.product_id).first()
        prod_title = prod.name if prod else "the item"

        if offer.status == NegotiationState.AUTO_ACCEPTED.value:
            return (
                f"Deal approved! We are delighted to accept your requested price of ₹{offer.offered_unit_price:,.2f} "
                f"per unit for {offer.quantity}x {prod_title} (Total: ₹{offer.final_total:,.2f}, saving ₹{offer.discount_amount:,.2f}). "
                f"Please review and accept your offer within {offer.metadata_json.get('ttl_minutes', 10)} minutes to lock in this pricing."
            )
        elif offer.status == NegotiationState.COUNTER_OFFERED.value:
            return (
                f"We reviewed your proposal. While we cannot meet ₹{offer.requested_unit_price:,.2f}, "
                f"our merchant policy allows us to offer our best rate of ₹{offer.offered_unit_price:,.2f} per unit "
                f"({offer.discount_percent:.1f}% discount, Total: ₹{offer.final_total:,.2f}). "
                f"Click [Accept Offer] if this works for you!"
            )
        elif offer.status == NegotiationState.HUMAN_APPROVAL_REQUIRED.value:
            return (
                f"Your requested discount on {offer.quantity}x {prod_title} exceeds automated approval limits. "
                f"We have escalated your proposal to our merchant team for review. You will receive an update shortly."
            )
        elif offer.status == NegotiationState.REJECTED.value:
            return (
                f"Thank you for your interest in {prod_title}. Unfortunately, we cannot accommodate this price request "
                f"as it exceeds our allowed discount thresholds ({offer.reason or 'exceeds merchant limits'}). "
                f"The regular list price of ₹{offer.list_unit_price:,.2f} applies."
            )
        return f"Offer status: {offer.status}. {offer.reason or ''}"
