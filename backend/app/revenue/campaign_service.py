import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.database.models.revenue_opportunity import RevenueOpportunity
from app.database.models.policy import Policy
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.revenue.schemas import RevenueOpportunityExecuteRequest, RevenueOpportunityResponse
from app.services.audit_service import AuditService

class RevenueCampaignService:
    """
    Revenue Campaign Lifecycle & Execution Service:
    Manages approval, rejection, and atomic campaign execution with real-time pre-execution re-validation.
    """

    @staticmethod
    def approve_opportunity(
        db: Session,
        merchant_id: str,
        opportunity_id: str,
        user_id: Optional[str] = None,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> RevenueOpportunity:
        assigned_trace = trace_id or f"trc_appr_opp_{uuid.uuid4().hex[:8]}"

        opp = db.query(RevenueOpportunity).filter(
            RevenueOpportunity.id == opportunity_id,
            RevenueOpportunity.merchant_id == merchant_id
        ).first()

        if not opp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Revenue opportunity '{opportunity_id}' not found for this merchant."
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Check expiration
        if opp.expires_at and now > opp.expires_at:
            opp.status = "EXPIRED"
            db.commit()
            AuditService.record_event(
                db=db,
                merchant_id=merchant_id,
                trace_id=assigned_trace,
                actor_type="SYSTEM",
                actor_id="RevenueCampaignService",
                action="OPPORTUNITY_EXPIRED",
                event_type="OPPORTUNITY_EXPIRED",
                status="EXPIRED",
                reason="Opportunity has expired",
                metadata_json={"opportunity_id": opp.id}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Revenue opportunity has expired and cannot be approved."
            )

        if opp.status == "EXECUTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Opportunity has already been executed."
            )

        # Policy validation before approval
        policy = db.query(Policy).filter(
            Policy.merchant_id == merchant_id,
            Policy.is_active == True
        ).order_by(Policy.version.desc()).first()

        max_disc = policy.max_discount_percent if policy else Decimal("5.00")
        if opp.proposed_discount_percent > max_disc:
            opp.status = "POLICY_BLOCKED"
            db.commit()
            AuditService.record_event(
                db=db,
                merchant_id=merchant_id,
                trace_id=assigned_trace,
                actor_type="SYSTEM",
                actor_id="RevenueCampaignService",
                action="AGENT_ACTION_BLOCKED",
                event_type="AGENT_ACTION_BLOCKED",
                status="BLOCKED",
                reason=f"Proposed discount of {opp.proposed_discount_percent}% exceeds active policy maximum of {max_disc}%.",
                metadata_json={"opportunity_id": opp.id, "proposed_discount": str(opp.proposed_discount_percent), "max_discount": str(max_disc)}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve: Proposed discount of {opp.proposed_discount_percent}% exceeds active policy maximum of {max_disc}%."
            )

        opp.status = "APPROVED"
        opp.approved_by_user_id = user_id or "merchant_admin"
        opp.approved_at = now
        db.commit()
        db.refresh(opp)

        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=assigned_trace,
            actor_type="USER",
            actor_id=user_id or "merchant_admin",
            action="MERCHANT_APPROVED",
            event_type="MERCHANT_APPROVED",
            status="SUCCESS",
            reason=reason or "Approved for live commerce execution",
            metadata_json={
                "opportunity_id": opp.id,
                "title": opp.title,
                "projected_net_value": str(opp.estimated_net_value) if opp.estimated_net_value else None
            }
        )

        return opp

    @staticmethod
    def reject_opportunity(
        db: Session,
        merchant_id: str,
        opportunity_id: str,
        user_id: Optional[str] = None,
        reason: str = "Merchant operator rejected proposal",
        trace_id: Optional[str] = None
    ) -> RevenueOpportunity:
        assigned_trace = trace_id or f"trc_rej_opp_{uuid.uuid4().hex[:8]}"

        opp = db.query(RevenueOpportunity).filter(
            RevenueOpportunity.id == opportunity_id,
            RevenueOpportunity.merchant_id == merchant_id
        ).first()

        if not opp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Revenue opportunity '{opportunity_id}' not found for this merchant."
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        opp.status = "REJECTED"
        opp.rejected_at = now
        opp.rejection_reason = reason
        db.commit()
        db.refresh(opp)

        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=assigned_trace,
            actor_type="USER",
            actor_id=user_id or "merchant_admin",
            action="MERCHANT_REJECTED",
            event_type="MERCHANT_REJECTED",
            status="REJECTED",
            reason=reason,
            metadata_json={
                "opportunity_id": opp.id,
                "title": opp.title
            }
        )

        return opp

    @staticmethod
    def execute_opportunity(
        db: Session,
        merchant_id: str,
        opportunity_id: str,
        req: RevenueOpportunityExecuteRequest
    ) -> RevenueOpportunity:
        assigned_trace = req.trace_id or f"trc_exec_opp_{uuid.uuid4().hex[:8]}"

        opp = db.query(RevenueOpportunity).filter(
            RevenueOpportunity.id == opportunity_id,
            RevenueOpportunity.merchant_id == merchant_id
        ).first()

        if not opp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Revenue opportunity '{opportunity_id}' not found for this merchant."
            )

        # Idempotent return if already executed with same idempotency_key or already in EXECUTED state
        if opp.status == "EXECUTED":
            if opp.idempotency_key == req.idempotency_key or opp.idempotency_key is not None:
                return opp
            return opp

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # 1. Expiration check
        if opp.expires_at and now > opp.expires_at:
            opp.status = "EXPIRED"
            db.commit()
            AuditService.record_event(
                db=db,
                merchant_id=merchant_id,
                trace_id=assigned_trace,
                actor_type="SYSTEM",
                actor_id="RevenueCampaignService",
                action="OPPORTUNITY_EXPIRED",
                event_type="OPPORTUNITY_EXPIRED",
                status="EXPIRED",
                reason="Cannot execute expired opportunity",
                metadata_json={"opportunity_id": opp.id}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="EXECUTION BLOCKED: Revenue opportunity has expired and cannot be executed."
            )

        # 2. Status check
        if opp.status == "REJECTED":
            AuditService.record_event(
                db=db,
                merchant_id=merchant_id,
                trace_id=assigned_trace,
                actor_type="SYSTEM",
                actor_id="RevenueCampaignService",
                action="AGENT_ACTION_BLOCKED",
                event_type="AGENT_ACTION_BLOCKED",
                status="BLOCKED",
                reason="Cannot execute rejected opportunity",
                metadata_json={"opportunity_id": opp.id}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="EXECUTION BLOCKED: A rejected opportunity cannot be executed."
            )

        if opp.status not in ("APPROVED", "SIMULATED", "GENERATED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot execute opportunity in status '{opp.status}'. Must be APPROVED or active."
            )

        # 3. Revalidate source and target products exist and are active
        target_ids = opp.target_product_ids or []
        if not target_ids and opp.inventory_impact:
            target_ids = opp.inventory_impact.get("target_product_ids") or []

        if opp.inventory_impact and opp.inventory_impact.get("target_stock") == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="EXECUTION BLOCKED BY INVENTORY: Target product is out of stock (0 units available)."
            )

        if opp.source_product_id:
            src_prod = db.query(Product).filter(Product.id == opp.source_product_id).first()
            if not src_prod or not src_prod.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"EXECUTION BLOCKED: Source product '{opp.source_product_id}' is inactive or deleted."
                )

        target_products = db.query(Product).filter(Product.id.in_(target_ids)).all() if target_ids else []
        for p in target_products:
            if not p.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"EXECUTION BLOCKED: Target product '{p.name}' is inactive."
                )
            inv = db.query(Inventory).filter(Inventory.product_id == p.id).first()
            stock = inv.stock_quantity if inv else (p.inventory.stock_quantity if p.inventory else 0)
            if stock <= 0:
                AuditService.record_event(
                    db=db,
                    merchant_id=merchant_id,
                    trace_id=assigned_trace,
                    actor_type="SYSTEM",
                    actor_id="RevenueCampaignService",
                    action="AGENT_ACTION_BLOCKED",
                    event_type="AGENT_ACTION_BLOCKED",
                    status="BLOCKED",
                    reason=f"Product '{p.name}' out of stock",
                    metadata_json={"opportunity_id": opp.id, "product_id": p.id}
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"EXECUTION BLOCKED BY INVENTORY: Product '{p.name}' is currently out of stock (0 units available)."
                )

        # Record Inventory Validated event
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=assigned_trace,
            actor_type="SYSTEM",
            actor_id="RevenueCampaignService",
            action="INVENTORY_VALIDATED",
            event_type="INVENTORY_VALIDATED",
            status="SUCCESS",
            metadata_json={"target_product_ids": target_ids}
        )

        # 4. Immediate Pre-Execution Policy Re-validation
        policy = db.query(Policy).filter(
            Policy.merchant_id == merchant_id,
            Policy.is_active == True
        ).order_by(Policy.version.desc()).first()

        max_disc = policy.max_discount_percent if policy else Decimal("5.00")
        if opp.proposed_discount_percent > max_disc:
            opp.status = "POLICY_BLOCKED"
            db.commit()
            AuditService.record_event(
                db=db,
                merchant_id=merchant_id,
                trace_id=assigned_trace,
                actor_type="SYSTEM",
                actor_id="RevenueCampaignService",
                action="AGENT_ACTION_BLOCKED",
                event_type="AGENT_ACTION_BLOCKED",
                status="BLOCKED",
                reason="Discount exceeds policy",
                metadata_json={"proposed": str(opp.proposed_discount_percent), "max": str(max_disc)}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"EXECUTION BLOCKED BY POLICY: Discount {opp.proposed_discount_percent}% exceeds policy threshold of {max_disc}%."
            )

        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=assigned_trace,
            actor_type="SYSTEM",
            actor_id="RevenueCampaignService",
            action="POLICY_EVALUATED",
            event_type="POLICY_EVALUATED",
            status="PASS",
            metadata_json={"max_discount": str(max_disc), "applied_discount": str(opp.proposed_discount_percent)}
        )

        # 5. Transition to EXECUTED with Idempotency Key
        opp.status = "EXECUTED"
        opp.idempotency_key = req.idempotency_key
        opp.executed_at = now
        opp.trace_id = assigned_trace
        db.commit()
        db.refresh(opp)

        # 6. Record Cryptographic Audit Trail Event
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=assigned_trace,
            actor_type="SYSTEM",
            actor_id="RevenueCampaignService",
            action="CAMPAIGN_EXECUTED",
            event_type="CAMPAIGN_EXECUTED",
            status="SUCCESS",
            new_state="EXECUTED",
            metadata_json={
                "opportunity_id": opp.id,
                "idempotency_key": req.idempotency_key,
                "executed_discount": str(opp.proposed_discount_percent),
                "projected_net_value": str(opp.estimated_net_value) if opp.estimated_net_value else None
            }
        )

        return opp

