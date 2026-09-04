from enum import Enum
from typing import Dict, Any

class FailureCategory(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    PROVIDER_4XX = "PROVIDER_4XX"
    PROVIDER_5XX = "PROVIDER_5XX"
    TIMEOUT = "TIMEOUT"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    UNKNOWN_PROVIDER_STATE = "UNKNOWN_PROVIDER_STATE"
    WEBHOOK_ERROR = "WEBHOOK_ERROR"
    RECONCILIATION_ERROR = "RECONCILIATION_ERROR"

class RecoveryAction(str, Enum):
    REJECT_IMMEDIATE = "REJECT_IMMEDIATE" # No retry, mark FAILED
    TRANSITION_UNKNOWN = "TRANSITION_UNKNOWN" # Mark UNKNOWN, trigger reconciliation
    RECONCILE_EXISTING = "RECONCILE_EXISTING" # Preserve known provider_order_id and reconcile
    RETRY_RECONCILIATION = "RETRY_RECONCILIATION" # Retain UNKNOWN, retry later

class FailureClassifier:
    """
    Deterministic failure classification engine mapping errors to recovery strategies.
    Distinguishes definitively known failures from ambiguous provider states.
    """

    @staticmethod
    def classify(error: Exception, provider_order_id_known: bool = False) -> Dict[str, Any]:
        err_str = str(error).lower()

        # Case B: If provider order ID is already known (e.g. downstream response parsing failed after order creation)
        if provider_order_id_known:
            return {
                "category": FailureCategory.UNKNOWN_PROVIDER_STATE,
                "recovery_action": RecoveryAction.RECONCILE_EXISTING,
                "is_ambiguous": True,
                "reason": f"Downstream failure after order creation: {str(error)}"
            }

        # Case A: Timeout or Connection Error
        if "timeout" in err_str or "timed out" in err_str:
            return {
                "category": FailureCategory.TIMEOUT,
                "recovery_action": RecoveryAction.TRANSITION_UNKNOWN,
                "is_ambiguous": True,
                "reason": f"Gateway connection timed out: {str(error)}"
            }

        if "connection" in err_str or "connect error" in err_str or "network" in err_str:
            return {
                "category": FailureCategory.CONNECTION_ERROR,
                "recovery_action": RecoveryAction.TRANSITION_UNKNOWN,
                "is_ambiguous": True,
                "reason": f"Network connection error: {str(error)}"
            }

        # 5xx Server Errors (Ambiguous whether provider created order before erroring)
        if "500" in err_str or "502" in err_str or "503" in err_str or "504" in err_str or "server error" in err_str:
            return {
                "category": FailureCategory.PROVIDER_5XX,
                "recovery_action": RecoveryAction.TRANSITION_UNKNOWN,
                "is_ambiguous": True,
                "reason": f"Provider 5xx Server Error: {str(error)}"
            }

        # Case C: 4xx Client Errors / Bad Request (Definitively rejected by provider before order creation)
        if "400" in err_str or "401" in err_str or "403" in err_str or "404" in err_str or "bad request" in err_str or "invalid" in err_str:
            return {
                "category": FailureCategory.PROVIDER_4XX,
                "recovery_action": RecoveryAction.REJECT_IMMEDIATE,
                "is_ambiguous": False,
                "reason": f"Provider 4xx Client Error: {str(error)}"
            }

        # Default fallback
        return {
            "category": FailureCategory.UNKNOWN_PROVIDER_STATE,
            "recovery_action": RecoveryAction.TRANSITION_UNKNOWN,
            "is_ambiguous": True,
            "reason": f"Unclassified failure: {str(error)}"
        }
