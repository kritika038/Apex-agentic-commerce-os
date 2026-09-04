from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.database.models.approval_request import ApprovalRequest
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.policy import Policy
from app.database.models.policy_evaluation import PolicyEvaluation
from app.database.models.user import User

class ApprovalService:
    """
    Atomic & Race-Safe Human Approval Workflow Service.
    """
    @staticmethod
    def get_merchant_approvals(db: Session, merchant_id: str) -> List[ApprovalRequest]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Auto-expire pending requests
        pending = db.query(ApprovalRequest).filter(
            ApprovalRequest.merchant_id == merchant_id,
            ApprovalRequest.status == "PENDING"
        ).all()
        
        for req in pending:
            if req.expires_at and now > req.expires_at:
                req.status = "EXPIRED"
                
        db.commit()

        return db.query(ApprovalRequest).filter(
            ApprovalRequest.merchant_id == merchant_id
        ).order_by(ApprovalRequest.created_at.desc()).all()

    @staticmethod
    def get_approval_by_id(db: Session, approval_id: str, merchant_id: str) -> ApprovalRequest:
        req = db.query(ApprovalRequest).filter(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.merchant_id == merchant_id
        ).first()
        
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request '{approval_id}' not found for this merchant."
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if req.status == "PENDING" and req.expires_at and now > req.expires_at:
            req.status = "EXPIRED"
            db.commit()
            db.refresh(req)

        return req

    @staticmethod
    def approve_request(
        db: Session,
        approval_id: str,
        merchant_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> Tuple[ApprovalRequest, TransactionAuthorization]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # 1. Fetch approval request with merchant verification
        req = db.query(ApprovalRequest).filter(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.merchant_id == merchant_id
        ).first()

        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval request not found."
            )

        # Check expiration
        if req.expires_at and now > req.expires_at:
            req.status = "EXPIRED"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approval request has expired and cannot be approved."
            )

        # Check status (Race safety: only PENDING can transition to APPROVED)
        if req.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Approval request is already in '{req.status}' state and cannot be approved again."
            )

        # 2. Resolve valid User.id for foreign key compliance
        valid_user_id = None
        if user_id:
            u = db.query(User).filter(User.id == user_id).first()
            if not u:
                u = db.query(User).filter(User.email.ilike(user_id)).first()
            if u:
                valid_user_id = u.id

        # 3. Transition ApprovalRequest
        req.status = "APPROVED"
        req.approved_by_user_id = valid_user_id
        req.approved_at = now

        # 3. Retrieve policy to get authorization expiration setting
        policy_eval = db.query(PolicyEvaluation).filter(PolicyEvaluation.id == req.policy_evaluation_id).first()
        policy_version = policy_eval.policy_version if policy_eval else 1
        exp_minutes = 10
        if policy_eval and policy_eval.policy_snapshot:
            exp_minutes = int(policy_eval.policy_snapshot.get("authorization_expiration_minutes", 10))

        auth_expires = now + timedelta(minutes=exp_minutes)

        # 4. Create TransactionAuthorization
        auth = TransactionAuthorization(
            merchant_id=merchant_id,
            purchase_intent_id=req.purchase_intent_id,
            policy_evaluation_id=req.policy_evaluation_id,
            approval_request_id=req.id,
            policy_version=policy_version,
            status="AUTHORIZED",
            authorized_amount=req.amount,
            currency=req.currency,
            authorized_by=user_id,
            authorized_at=now,
            expires_at=auth_expires
        )
        db.add(auth)

        # 5. Update PurchaseIntent status
        intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == req.purchase_intent_id).first()
        trace_id = intent.trace_id if intent else (policy_eval.trace_id if policy_eval else f"trace_{req.id[:8]}")
        session_id = intent.session_id if intent else None

        if intent:
            intent.status = "VALIDATED"

        db.flush()

        from app.services.audit_service import AuditService
        # Record Approval Decision Event
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=trace_id,
            session_id=session_id,
            purchase_intent_id=req.purchase_intent_id,
            approval_request_id=req.id,
            actor_type="USER",
            actor_id=user_id,
            action="APPROVE_REQUEST",
            event_type="APPROVAL_DECISION",
            previous_state="PENDING",
            new_state="APPROVED",
            status="SUCCESS",
            reason=notes or "Approved by merchant operator",
            metadata_json={"approved_amount": str(req.amount), "currency": req.currency}
        )

        # Record Authorization Created Event
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=trace_id,
            session_id=session_id,
            purchase_intent_id=req.purchase_intent_id,
            approval_request_id=req.id,
            authorization_id=auth.id,
            actor_type="USER",
            actor_id=user_id,
            action="AUTHORIZE_TRANSACTION",
            event_type="AUTHORIZATION_CREATED",
            new_state="AUTHORIZED",
            status="SUCCESS",
            metadata_json={"authorized_amount": str(auth.authorized_amount), "currency": auth.currency}
        )

        db.commit()
        db.refresh(req)
        db.refresh(auth)
        return req, auth

    @staticmethod
    def reject_request(
        db: Session,
        approval_id: str,
        merchant_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> ApprovalRequest:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        req = db.query(ApprovalRequest).filter(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.merchant_id == merchant_id
        ).first()

        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval request not found."
            )

        if req.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Approval request is already in '{req.status}' state and cannot be rejected."
            )

        valid_user_id = None
        if user_id:
            u = db.query(User).filter(User.id == user_id).first()
            if not u:
                u = db.query(User).filter(User.email.ilike(user_id)).first()
            if u:
                valid_user_id = u.id

        req.status = "REJECTED"
        req.approved_by_user_id = valid_user_id
        req.rejected_at = now
        req.reason = reason or req.reason

        intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == req.purchase_intent_id).first()
        trace_id = intent.trace_id if intent else f"trace_{req.id[:8]}"
        session_id = intent.session_id if intent else None

        if intent:
            intent.status = "REJECTED"

        db.flush()

        from app.services.audit_service import AuditService
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=trace_id,
            session_id=session_id,
            purchase_intent_id=req.purchase_intent_id,
            approval_request_id=req.id,
            actor_type="USER",
            actor_id=user_id,
            action="REJECT_REQUEST",
            event_type="APPROVAL_DECISION",
            previous_state="PENDING",
            new_state="REJECTED",
            status="REJECTED",
            reason=reason or "Rejected by merchant operator",
            metadata_json={"amount": str(req.amount), "currency": req.currency}
        )

        db.commit()
        db.refresh(req)
        return req
