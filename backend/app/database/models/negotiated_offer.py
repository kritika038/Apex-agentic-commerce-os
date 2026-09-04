from decimal import Decimal
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, Integer, Boolean, ForeignKey, DateTime, Index
from .base import TimeStampedBase, generate_uuid


class NegotiatedOffer(TimeStampedBase):
    __tablename__ = "negotiated_offers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, index=True)
    negotiation_id: Mapped[str] = mapped_column(String, index=True)
    buyer_user_id: Mapped[str] = mapped_column(String, index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    variant_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    # Monetary fields (Strict Decimal)
    list_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    list_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    requested_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    merchant_counter_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    final_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String, default="INR")

    # Conversation Context & Explanations
    buyer_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    merchant_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # State machine
    status: Mapped[str] = mapped_column(String, default="NEGOTIATION_STARTED", index=True)
    merchant_decision: Mapped[str] = mapped_column(String, default="EVALUATING") # AUTO_ACCEPT, COUNTER, HUMAN_APPROVAL, REJECT
    merchant_decision_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    merchant_approval_request_id: Mapped[Optional[str]] = mapped_column(ForeignKey("approval_requests.id"), nullable=True)

    # Acceptance tracking
    customer_acceptance_required: Mapped[bool] = mapped_column(Boolean, default=True)
    customer_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    customer_rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    buyer_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Expiry
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    # Governance & Payment Linking
    governance_evaluation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("policy_evaluations.id"), nullable=True)
    transaction_authorization_id: Mapped[Optional[str]] = mapped_column(ForeignKey("transaction_authorizations.id"), nullable=True)
    payment_order_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    order_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    # Relationships
    merchant = relationship("Merchant")
    product = relationship("Product")
    merchant_approval_request = relationship("ApprovalRequest")
    governance_evaluation = relationship("PolicyEvaluation")
    transaction_authorization = relationship("TransactionAuthorization")

    __table_args__ = (
        Index("ix_negotiated_offers_tenant_status", "tenant_id", "status"),
        Index("ix_negotiated_offers_buyer_status", "buyer_user_id", "status"),
        Index("ix_negotiated_offers_expiry", "expires_at", "status"),
    )

    @property
    def offer_code(self) -> str:
        return self.negotiation_id

    @property
    def customer_id(self) -> str:
        return self.buyer_user_id

    @property
    def product_name(self) -> Optional[str]:
        return self.product.name if self.product else None

    @property
    def list_unit_price(self) -> Decimal:
        return self.list_price

    @property
    def requested_unit_price(self) -> Decimal:
        if not self.quantity:
            return self.requested_total
        return (self.requested_total / Decimal(self.quantity)).quantize(Decimal("0.01"))

    @property
    def offered_unit_price(self) -> Decimal:
        if not self.quantity:
            return self.final_total
        return (self.final_total / Decimal(self.quantity)).quantize(Decimal("0.01"))

    @property
    def offered_total(self) -> Decimal:
        return self.final_total

    @property
    def reason(self) -> Optional[str]:
        return self.merchant_message

    @property
    def is_active(self) -> bool:
        return self.status not in ["REJECTED", "MERCHANT_REJECTED", "CUSTOMER_REJECTED", "EXPIRED", "ORDER_CONFIRMED"]

    @property
    def requires_human_approval(self) -> bool:
        return self.status == "HUMAN_APPROVAL_REQUIRED" or bool(self.merchant_approval_request_id)

    @property
    def customer_accepted(self) -> bool:
        return bool(self.customer_accepted_at or self.buyer_accepted_at or self.status in ["CUSTOMER_ACCEPTED", "PAYMENT_PENDING", "ORDER_CONFIRMED"])

    @property
    def approval_request_id(self) -> Optional[str]:
        return self.merchant_approval_request_id

    @property
    def audit_hash(self) -> Optional[str]:
        # Return 64-character SHA-256 hash representation from trace or hash
        import hashlib
        return hashlib.sha256(f"{self.id}:{self.status}:{self.final_total}".encode("utf-8")).hexdigest()

    @property
    def payment_status(self) -> Optional[str]:
        if self.status == "ORDER_CONFIRMED":
            return "COMPLETED"
        if self.status == "PAYMENT_PENDING":
            return "PENDING"
        return None

    @property
    def metadata_json(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "ttl_minutes": 10,
            "policy_evaluation": {"status": self.status, "merchant_decision": self.merchant_decision}
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "negotiation_id": self.negotiation_id,
            "buyer_user_id": self.buyer_user_id,
            "merchant_id": self.merchant_id,
            "product_id": self.product_id,
            "variant_id": self.variant_id,
            "quantity": self.quantity,
            "list_price": float(self.list_price),
            "list_total": float(self.list_total),
            "requested_total": float(self.requested_total),
            "merchant_counter_total": float(self.merchant_counter_total) if self.merchant_counter_total else None,
            "final_total": float(self.final_total),
            "discount_amount": float(self.discount_amount),
            "discount_percent": float(self.discount_percent),
            "currency": self.currency,
            "buyer_message": self.buyer_message,
            "merchant_message": self.merchant_message,
            "status": self.status,
            "merchant_decision": self.merchant_decision,
            "merchant_decision_at": self.merchant_decision_at.isoformat() if self.merchant_decision_at else None,
            "customer_acceptance_required": self.customer_acceptance_required,
            "customer_accepted_at": self.customer_accepted_at.isoformat() if self.customer_accepted_at else None,
            "customer_rejected_at": self.customer_rejected_at.isoformat() if self.customer_rejected_at else None,
            "expires_at": self.expires_at.isoformat(),
            "payment_order_id": self.payment_order_id,
            "order_id": self.order_id,
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
