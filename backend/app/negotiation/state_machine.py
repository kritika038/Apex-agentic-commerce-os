"""
Deterministic Server-Side Negotiation State Machine.
Enforces valid transitions and terminal states for all Buyer <-> Merchant agent negotiations.
"""

from typing import Set, Dict
from enum import Enum


class NegotiationState(str, Enum):
    NEGOTIATION_STARTED = "NEGOTIATION_STARTED"
    BUYER_INTENT_RESOLVED = "BUYER_INTENT_RESOLVED"
    OFFER_REQUESTED = "OFFER_REQUESTED"
    MERCHANT_POLICY_EVALUATING = "MERCHANT_POLICY_EVALUATING"
    
    # Decisions
    AUTO_ACCEPTED = "AUTO_ACCEPTED"
    COUNTER_OFFERED = "COUNTER_OFFERED"
    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
    
    # Merchant Admin actions
    MERCHANT_APPROVED = "MERCHANT_APPROVED"
    MERCHANT_COUNTERED = "MERCHANT_COUNTERED"
    MERCHANT_REJECTED = "MERCHANT_REJECTED"
    
    # Customer Presentation & Decision
    CUSTOMER_OFFER_PRESENTED = "CUSTOMER_OFFER_PRESENTED"
    CUSTOMER_ACCEPTED = "CUSTOMER_ACCEPTED"
    CUSTOMER_REJECTED = "CUSTOMER_REJECTED"
    
    # Governance & Payment progression
    GOVERNANCE_EVALUATED = "GOVERNANCE_EVALUATED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_VERIFIED = "PAYMENT_VERIFIED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    
    # Terminal / Failure states
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES: Set[NegotiationState] = {
    NegotiationState.ORDER_CONFIRMED,
    NegotiationState.CUSTOMER_REJECTED,
    NegotiationState.MERCHANT_REJECTED,
    NegotiationState.REJECTED,
    NegotiationState.EXPIRED,
    NegotiationState.CANCELLED,
}

# Explicit graph of valid state transitions
VALID_TRANSITIONS: Dict[NegotiationState, Set[NegotiationState]] = {
    NegotiationState.NEGOTIATION_STARTED: {
        NegotiationState.BUYER_INTENT_RESOLVED,
        NegotiationState.OFFER_REQUESTED,
        NegotiationState.REJECTED,
        NegotiationState.CANCELLED,
    },
    NegotiationState.BUYER_INTENT_RESOLVED: {
        NegotiationState.OFFER_REQUESTED,
        NegotiationState.REJECTED,
        NegotiationState.CANCELLED,
    },
    NegotiationState.OFFER_REQUESTED: {
        NegotiationState.MERCHANT_POLICY_EVALUATING,
        NegotiationState.AUTO_ACCEPTED,
        NegotiationState.COUNTER_OFFERED,
        NegotiationState.HUMAN_APPROVAL_REQUIRED,
        NegotiationState.REJECTED,
        NegotiationState.EXPIRED,
    },
    NegotiationState.MERCHANT_POLICY_EVALUATING: {
        NegotiationState.AUTO_ACCEPTED,
        NegotiationState.COUNTER_OFFERED,
        NegotiationState.HUMAN_APPROVAL_REQUIRED,
        NegotiationState.REJECTED,
        NegotiationState.EXPIRED,
    },
    NegotiationState.AUTO_ACCEPTED: {
        NegotiationState.CUSTOMER_OFFER_PRESENTED,
        NegotiationState.CUSTOMER_ACCEPTED,
        NegotiationState.EXPIRED,
        NegotiationState.CANCELLED,
    },
    NegotiationState.COUNTER_OFFERED: {
        NegotiationState.CUSTOMER_OFFER_PRESENTED,
        NegotiationState.CUSTOMER_ACCEPTED,
        NegotiationState.CUSTOMER_REJECTED,
        NegotiationState.EXPIRED,
        NegotiationState.CANCELLED,
    },
    NegotiationState.HUMAN_APPROVAL_REQUIRED: {
        NegotiationState.MERCHANT_APPROVED,
        NegotiationState.MERCHANT_COUNTERED,
        NegotiationState.MERCHANT_REJECTED,
        NegotiationState.EXPIRED,
        NegotiationState.CANCELLED,
    },
    NegotiationState.MERCHANT_APPROVED: {
        NegotiationState.CUSTOMER_OFFER_PRESENTED,
        NegotiationState.CUSTOMER_ACCEPTED,
        NegotiationState.EXPIRED,
        NegotiationState.CANCELLED,
    },
    NegotiationState.MERCHANT_COUNTERED: {
        NegotiationState.CUSTOMER_OFFER_PRESENTED,
        NegotiationState.CUSTOMER_ACCEPTED,
        NegotiationState.CUSTOMER_REJECTED,
        NegotiationState.EXPIRED,
        NegotiationState.CANCELLED,
    },
    NegotiationState.CUSTOMER_OFFER_PRESENTED: {
        NegotiationState.CUSTOMER_ACCEPTED,
        NegotiationState.CUSTOMER_REJECTED,
        NegotiationState.EXPIRED,
        NegotiationState.CANCELLED,
    },
    NegotiationState.CUSTOMER_ACCEPTED: {
        NegotiationState.GOVERNANCE_EVALUATED,
        NegotiationState.PAYMENT_PENDING,
        NegotiationState.EXPIRED,
        NegotiationState.CANCELLED,
    },
    NegotiationState.GOVERNANCE_EVALUATED: {
        NegotiationState.PAYMENT_PENDING,
        NegotiationState.REJECTED,
        NegotiationState.EXPIRED,
        NegotiationState.CANCELLED,
    },
    NegotiationState.PAYMENT_PENDING: {
        NegotiationState.PAYMENT_VERIFIED,
        NegotiationState.ORDER_CONFIRMED,
        NegotiationState.REJECTED,
        NegotiationState.EXPIRED,
        NegotiationState.CANCELLED,
    },
    NegotiationState.PAYMENT_VERIFIED: {
        NegotiationState.ORDER_CONFIRMED,
        NegotiationState.CANCELLED,
    },
    # Terminal states have no outgoing transitions
    NegotiationState.ORDER_CONFIRMED: set(),
    NegotiationState.CUSTOMER_REJECTED: set(),
    NegotiationState.MERCHANT_REJECTED: set(),
    NegotiationState.REJECTED: set(),
    NegotiationState.EXPIRED: set(),
    NegotiationState.CANCELLED: set(),
}


class StateTransitionError(Exception):
    """Raised when an illegal negotiation state transition is attempted."""
    pass


class NegotiationStateMachine:
    """
    Validates and performs deterministic state transitions.
    Guarantees that clients cannot jump states or force approvals without server verification.
    """

    @staticmethod
    def validate_transition(from_state: str, to_state: str) -> bool:
        """
        Returns True if transition is valid or idempotent (from == to).
        Raises StateTransitionError if illegal.
        """
        if from_state == to_state:
            return True  # Idempotent re-affirmation

        try:
            from_enum = NegotiationState(from_state)
            to_enum = NegotiationState(to_state)
        except ValueError as e:
            raise StateTransitionError(f"Invalid state identifier: {e}")

        # Any active state can transition to EXPIRED or CANCELLED
        if to_enum in {NegotiationState.EXPIRED, NegotiationState.CANCELLED} and from_enum not in TERMINAL_STATES:
            return True

        allowed = VALID_TRANSITIONS.get(from_enum, set())
        if to_enum not in allowed:
            raise StateTransitionError(
                f"Illegal negotiation transition from {from_state} to {to_state}. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            )
        return True

    @staticmethod
    def is_terminal(state: str) -> bool:
        try:
            return NegotiationState(state) in TERMINAL_STATES
        except ValueError:
            return False

    @staticmethod
    def can_accept(state: str) -> bool:
        """Only offers presented to customer or approved can be accepted."""
        return state in {
            NegotiationState.AUTO_ACCEPTED.value,
            NegotiationState.COUNTER_OFFERED.value,
            NegotiationState.MERCHANT_APPROVED.value,
            NegotiationState.MERCHANT_COUNTERED.value,
            NegotiationState.CUSTOMER_OFFER_PRESENTED.value,
        }

    @staticmethod
    def can_checkout(state: str) -> bool:
        """Only customer-accepted offers can proceed to payment checkout."""
        return state in {
            NegotiationState.CUSTOMER_ACCEPTED.value,
            NegotiationState.GOVERNANCE_EVALUATED.value,
            NegotiationState.PAYMENT_PENDING.value,
        }
