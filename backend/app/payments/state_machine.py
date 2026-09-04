from datetime import datetime, timezone
from typing import Set, Dict, Optional
from sqlalchemy.orm import Session

class PaymentState:
    CREATED = "CREATED"
    ORDER_CREATING = "ORDER_CREATING"
    ORDER_CREATED = "ORDER_CREATED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    RECONCILING = "RECONCILING"
    CANCELLED = "CANCELLED"

# Define valid state transitions
VALID_TRANSITIONS: Dict[str, Set[str]] = {
    PaymentState.CREATED: {PaymentState.ORDER_CREATING},
    PaymentState.ORDER_CREATING: {
        PaymentState.ORDER_CREATED,
        PaymentState.UNKNOWN,
        PaymentState.FAILED
    },
    PaymentState.ORDER_CREATED: {
        PaymentState.PAYMENT_PENDING,
        PaymentState.AUTHORIZED,
        PaymentState.CAPTURED,
        PaymentState.FAILED,
        PaymentState.CANCELLED,
        PaymentState.UNKNOWN,
        PaymentState.RECONCILING
    },
    PaymentState.PAYMENT_PENDING: {
        PaymentState.AUTHORIZED,
        PaymentState.CAPTURED,
        PaymentState.FAILED,
        PaymentState.UNKNOWN,
        PaymentState.CANCELLED,
        PaymentState.RECONCILING
    },
    PaymentState.AUTHORIZED: {
        PaymentState.CAPTURED,
        PaymentState.FAILED,
        PaymentState.CANCELLED
    },
    PaymentState.UNKNOWN: {
        PaymentState.RECONCILING,
        PaymentState.FAILED,
        PaymentState.CAPTURED
    },
    PaymentState.RECONCILING: {
        PaymentState.CAPTURED,
        PaymentState.FAILED,
        PaymentState.CANCELLED,
        PaymentState.ORDER_CREATED,
        PaymentState.PAYMENT_PENDING,
        PaymentState.UNKNOWN
    },
    PaymentState.FAILED: set(), # Terminal
    PaymentState.CAPTURED: set(), # Terminal (Settled - immune to downgrades)
    PaymentState.CANCELLED: set() # Terminal
}

class InvalidStateTransitionError(Exception):
    def __init__(self, current_state: str, new_state: str):
        super().__init__(f"Invalid payment state transition from '{current_state}' to '{new_state}'.")
        self.current_state = current_state
        self.new_state = new_state

class PaymentStateMachine:
    """
    Centralized Payment State Machine.
    Validates all state transitions, guarantees terminal state immunity, and records audit timestamps.
    """

    @staticmethod
    def is_valid_transition(current_state: str, new_state: str) -> bool:
        if current_state == new_state:
            return True
        return new_state in VALID_TRANSITIONS.get(current_state, set())

    @staticmethod
    def validate_transition(current_state: str, new_state: str) -> None:
        if not PaymentStateMachine.is_valid_transition(current_state, new_state):
            raise InvalidStateTransitionError(current_state, new_state)

    @staticmethod
    def is_terminal(state: str) -> bool:
        return state in (PaymentState.CAPTURED, PaymentState.FAILED, PaymentState.CANCELLED)

    @staticmethod
    def transition(
        transaction,
        to_state: str,
        reason: Optional[str] = None,
        error_code: Optional[str] = None,
        db: Optional[Session] = None
    ):
        """
        Executes a validated state transition on a PaymentTransaction.
        """
        current_state = transaction.status
        if current_state == to_state:
            return transaction

        PaymentStateMachine.validate_transition(current_state, to_state)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        transaction.status = to_state

        if to_state == PaymentState.CAPTURED:
            transaction.captured_at = now
        elif to_state == PaymentState.AUTHORIZED:
            transaction.authorized_at = now
        elif to_state == PaymentState.FAILED:
            transaction.failed_at = now
            if error_code:
                transaction.failure_code = error_code
            if reason:
                transaction.failure_message = reason
        elif to_state == PaymentState.UNKNOWN:
            if error_code:
                transaction.failure_code = error_code
            if reason:
                transaction.failure_message = reason

        if db:
            db.commit()
            db.refresh(transaction)

        return transaction
