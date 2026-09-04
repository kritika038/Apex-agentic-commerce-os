import pytest
from app.payments.state_machine import PaymentStateMachine, PaymentState, InvalidStateTransitionError

def test_valid_state_transitions():
    """
    Verifies that all standard lifecycle state transitions pass validation.
    """
    assert PaymentStateMachine.is_valid_transition(PaymentState.CREATED, PaymentState.ORDER_CREATING)
    assert PaymentStateMachine.is_valid_transition(PaymentState.ORDER_CREATING, PaymentState.ORDER_CREATED)
    assert PaymentStateMachine.is_valid_transition(PaymentState.ORDER_CREATING, PaymentState.UNKNOWN)
    assert PaymentStateMachine.is_valid_transition(PaymentState.ORDER_CREATED, PaymentState.PAYMENT_PENDING)
    assert PaymentStateMachine.is_valid_transition(PaymentState.PAYMENT_PENDING, PaymentState.CAPTURED)
    assert PaymentStateMachine.is_valid_transition(PaymentState.UNKNOWN, PaymentState.RECONCILING)
    assert PaymentStateMachine.is_valid_transition(PaymentState.RECONCILING, PaymentState.CAPTURED)
    assert PaymentStateMachine.is_valid_transition(PaymentState.RECONCILING, PaymentState.FAILED)
    assert PaymentStateMachine.is_valid_transition(PaymentState.RECONCILING, PaymentState.ORDER_CREATED)

def test_invalid_state_transitions():
    """
    Verifies that illegal state transitions are rejected with InvalidStateTransitionError.
    """
    # Cannot jump from CREATED directly to CAPTURED
    with pytest.raises(InvalidStateTransitionError):
        PaymentStateMachine.validate_transition(PaymentState.CREATED, PaymentState.CAPTURED)

    # CAPTURED terminal state cannot be downgraded
    with pytest.raises(InvalidStateTransitionError):
        PaymentStateMachine.validate_transition(PaymentState.CAPTURED, PaymentState.FAILED)

    with pytest.raises(InvalidStateTransitionError):
        PaymentStateMachine.validate_transition(PaymentState.CAPTURED, PaymentState.UNKNOWN)

    with pytest.raises(InvalidStateTransitionError):
        PaymentStateMachine.validate_transition(PaymentState.CAPTURED, PaymentState.RECONCILING)

    with pytest.raises(InvalidStateTransitionError):
        PaymentStateMachine.validate_transition(PaymentState.CAPTURED, PaymentState.ORDER_CREATED)

    # FAILED terminal state cannot be altered
    with pytest.raises(InvalidStateTransitionError):
        PaymentStateMachine.validate_transition(PaymentState.FAILED, PaymentState.CAPTURED)

    with pytest.raises(InvalidStateTransitionError):
        PaymentStateMachine.validate_transition(PaymentState.FAILED, PaymentState.PAYMENT_PENDING)

def test_terminal_state_detection():
    """
    Verifies terminal state detection for CAPTURED, FAILED, and CANCELLED.
    """
    assert PaymentStateMachine.is_terminal(PaymentState.CAPTURED) is True
    assert PaymentStateMachine.is_terminal(PaymentState.FAILED) is True
    assert PaymentStateMachine.is_terminal(PaymentState.CANCELLED) is True
    assert PaymentStateMachine.is_terminal(PaymentState.ORDER_CREATED) is False
    assert PaymentStateMachine.is_terminal(PaymentState.UNKNOWN) is False
    assert PaymentStateMachine.is_terminal(PaymentState.RECONCILING) is False
