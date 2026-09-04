from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.purchase_intent import PurchaseIntent

class AuthorizationService:
    """
    Reusable service for validating transaction authorizations.
    Serves as the strict security input boundary consumed by Phase 5.
    """
    @staticmethod
    def validate_authorization(
        db: Session,
        authorization_id: str,
        merchant_id: str,
        expected_amount: Optional[Decimal] = None,
        expected_currency: Optional[str] = None
    ) -> Tuple[bool, str, Optional[TransactionAuthorization]]:
        auth = db.query(TransactionAuthorization).filter(
            TransactionAuthorization.id == authorization_id,
            TransactionAuthorization.merchant_id == merchant_id
        ).first()

        if not auth:
            return False, "Transaction authorization not found for this merchant.", None

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Check expiration
        if auth.expires_at and now > auth.expires_at:
            if auth.status == "AUTHORIZED":
                auth.status = "EXPIRED"
                db.commit()
                db.refresh(auth)
            return False, "Transaction authorization has expired.", auth

        # Check status
        if auth.status != "AUTHORIZED":
            return False, f"Transaction authorization is in '{auth.status}' status (must be AUTHORIZED).", auth

        # Check amount binding
        if expected_amount is not None:
            auth_amt = Decimal(str(auth.authorized_amount))
            exp_amt = Decimal(str(expected_amount))
            if auth_amt != exp_amt:
                return False, f"Amount mismatch: Authorized amount (₹{auth_amt:,.2f}) does not match expected amount (₹{exp_amt:,.2f}).", auth

        # Check currency binding
        if expected_currency is not None and auth.currency != expected_currency:
            return False, f"Currency mismatch: Authorized currency '{auth.currency}' != Expected '{expected_currency}'.", auth

        # Verify linked PurchaseIntent or NegotiatedOffer
        intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == auth.purchase_intent_id).first()
        if not intent or intent.status in ("REJECTED", "EXPIRED"):
            from app.database.models.negotiated_offer import NegotiatedOffer
            neg_offer = db.query(NegotiatedOffer).filter(
                (NegotiatedOffer.negotiation_id == auth.purchase_intent_id) | (NegotiatedOffer.id == auth.purchase_intent_id)
            ).first()
            if not neg_offer or neg_offer.status in ("REJECTED", "EXPIRED", "CUSTOMER_REJECTED", "MERCHANT_REJECTED"):
                return False, f"Linked Purchase Intent or Negotiated Offer '{auth.purchase_intent_id}' is invalid or expired.", auth

        return True, "Authorization is valid and active.", auth
