from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.database.models.user import User
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent

class CustomerAnalyticsService:
    """
    Computes transparent customer segments and metrics from real order records.
    """

    @staticmethod
    def get_customer_segments(
        db: Session,
        merchant_id: str
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        thirty_days_ago = now - timedelta(days=30)
        sixty_days_ago = now - timedelta(days=60)

        # Query all captured transactions
        txs = db.query(PaymentTransaction).filter(
            PaymentTransaction.merchant_id == merchant_id,
            PaymentTransaction.status == "CAPTURED"
        ).all()

        user_spending: Dict[str, Decimal] = {}
        user_order_counts: Dict[str, int] = {}
        user_last_active: Dict[str, datetime] = {}

        for tx in txs:
            intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == tx.purchase_intent_id).first() if tx.purchase_intent_id else None
            buyer_id = intent.buyer_id if intent else (tx.user_id or "anonymous_shopper")

            user_spending[buyer_id] = user_spending.get(buyer_id, Decimal("0.00")) + Decimal(str(tx.amount))
            user_order_counts[buyer_id] = user_order_counts.get(buyer_id, 0) + 1
            if buyer_id not in user_last_active or (tx.created_at and tx.created_at > user_last_active[buyer_id]):
                user_last_active[buyer_id] = tx.created_at or now

        total_customers = len(user_spending)
        new_customers = 0
        repeat_customers = 0
        high_value = 0
        dormant = 0
        active_recent = 0

        for buyer_id, count in user_order_counts.items():
            spent = user_spending[buyer_id]
            last_date = user_last_active.get(buyer_id, now)

            if count == 1:
                new_customers += 1
            else:
                repeat_customers += 1

            if spent >= Decimal("5000.00"):
                high_value += 1

            if last_date >= thirty_days_ago:
                active_recent += 1
            elif last_date < sixty_days_ago:
                dormant += 1

        segments = [
            {
                "segment_key": "REPEAT_CUSTOMERS",
                "name": "Repeat & Loyal Buyers",
                "count": repeat_customers,
                "description": "Shoppers with 2+ captured orders",
                "strategy": "VIP rewards, early access offers"
            },
            {
                "segment_key": "HIGH_VALUE_BUYERS",
                "name": "High-Value Shoppers (₹5,000+)",
                "count": high_value,
                "description": "Lifetime spending exceeding ₹5,000",
                "strategy": "Premium gear upsells, personalized concierge"
            },
            {
                "segment_key": "NEW_CUSTOMERS",
                "name": "First-Time Customers",
                "count": new_customers,
                "description": "Single order completed",
                "strategy": "Cross-sell accessories & onboarding coupon"
            },
            {
                "segment_key": "DORMANT_CUSTOMERS",
                "name": "Dormant Accounts (>60 days)",
                "count": dormant,
                "description": "No order activity in the last 60 days",
                "strategy": "Win-back discount & seasonal collection update"
            }
        ]

        return {
            "total_unique_buyers": total_customers,
            "repeat_purchase_rate": round(repeat_customers / max(1, total_customers), 2),
            "recently_active_buyers": active_recent,
            "segments": segments
        }
