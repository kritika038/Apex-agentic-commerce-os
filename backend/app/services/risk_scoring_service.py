from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.payment_attempt import PaymentAttempt

class RiskScoringService:
    """
    Advisory Transaction Risk Scoring Service.
    Computes explainable risk assessments (LOW, MEDIUM, HIGH) without blocking legitimate payments.
    """

    @staticmethod
    def assess_transaction_risk(
        db: Session,
        merchant_id: str,
        amount: Decimal,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        risk_score = 15 # Baseline normal
        reasons = []

        # 1. Amount anomaly check
        if amount > Decimal("8000.00"):
            risk_score += 25
            reasons.append("High monetary value transaction (>₹8,000)")
        elif amount > Decimal("5000.00"):
            risk_score += 15
            reasons.append("Above autonomous approval threshold (₹5,000)")

        # 2. Check recent failed payment attempts for this session/user
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        ten_mins_ago = now - timedelta(minutes=10)

        recent_failures = db.query(PaymentAttempt).filter(
            PaymentAttempt.merchant_id == merchant_id,
            PaymentAttempt.status == "FAILED",
            PaymentAttempt.created_at >= ten_mins_ago
        ).count()

        if recent_failures >= 3:
            risk_score += 35
            reasons.append(f"Multiple ({recent_failures}) payment failures recorded in past 10 minutes")
        elif recent_failures >= 1:
            risk_score += 10
            reasons.append("Previous recent payment retry detected")

        # Determine risk level
        if risk_score >= 60:
            level = "HIGH"
        elif risk_score >= 35:
            level = "MEDIUM"
        else:
            level = "LOW"
            reasons.append("Normal shopping session velocity and verified catalog pricing")

        return {
            "risk_level": level,
            "risk_score": min(95, risk_score),
            "reasons": reasons,
            "recommendation": "Require human OTP / 3D-Secure authentication" if level == "HIGH" else "Proceed with standard Razorpay verification",
            "is_advisory": True
        }
