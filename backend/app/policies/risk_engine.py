from decimal import Decimal
from typing import Dict, Any, List
from app.database.models.policy import Policy

class RiskEngine:
    """
    Deterministic Financial Risk Assessment Engine.
    
    Principles:
    - 100% deterministic (zero LLM calls).
    - Uses exact Decimal comparisons.
    - Transparent risk justification.
    """
    @staticmethod
    def evaluate_risk(
        amount: Decimal,
        quantity: int,
        policy: Policy,
        violations: List[str]
    ) -> Dict[str, Any]:
        reasons: List[str] = []
        
        # 1. Any hard violation immediately escalates risk to HIGH
        if violations:
            reasons.append(f"Hard policy violation detected: {'; '.join(violations)}")
            return {
                "risk_level": "HIGH",
                "reasons": reasons
            }

        # 2. Check if amount exceeds human approval threshold
        if amount > policy.approval_threshold:
            reasons.append(
                f"Transaction amount (₹{amount:,.2f}) exceeds automatic approval threshold (₹{policy.approval_threshold:,.2f})."
            )
            return {
                "risk_level": "HIGH",
                "reasons": reasons
            }

        # 3. Check if amount is in MEDIUM risk band (between low_risk_limit and approval_threshold)
        if amount > policy.low_risk_limit:
            reasons.append(
                f"Transaction amount (₹{amount:,.2f}) exceeds low-risk threshold (₹{policy.low_risk_limit:,.2f}) but is within automatic limit."
            )
            return {
                "risk_level": "MEDIUM",
                "reasons": reasons
            }

        # 4. Standard Low Risk
        reasons.append(
            f"Transaction amount (₹{amount:,.2f}) is within standard low-risk boundary (₹{policy.low_risk_limit:,.2f}) with zero policy violations."
        )
        return {
            "risk_level": "LOW",
            "reasons": reasons
        }
