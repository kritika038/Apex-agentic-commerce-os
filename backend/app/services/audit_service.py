import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database.models.audit_event import AuditEvent
from app.database.models.audit_trace_head import AuditTraceHead
from app.services.audit_integrity_service import AuditIntegrityService, GENESIS_HASH
from app.utils.redaction import redact_sensitive_data

logger = logging.getLogger(__name__)

# Security-critical events that must fail-closed if audit recording fails
CRITICAL_ACTIONS = {
    "EVALUATE_POLICY",
    "APPROVE_REQUEST",
    "REJECT_REQUEST",
    "CREATE_PAYMENT_ORDER",
    "PROCESS_WEBHOOK",
    "RECONCILE_PAYMENT",
    "AUTHORIZE_TRANSACTION"
}

class AuditService:
    """
    Authoritative, immutable audit event recording and querying service.
    Guarantees monotonic sequence numbers and fork-free cryptographic hash chaining.
    """

    @staticmethod
    def record_event(
        db: Session,
        merchant_id: str,
        trace_id: str,
        actor_type: str,
        action: str,
        event_type: str,
        status: str = "SUCCESS",
        actor_id: Optional[str] = None,
        session_id: Optional[str] = None,
        purchase_intent_id: Optional[str] = None,
        order_id: Optional[str] = None,
        payment_transaction_id: Optional[str] = None,
        payment_attempt_id: Optional[str] = None,
        authorization_id: Optional[str] = None,
        approval_request_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        agent_version: Optional[str] = None,
        webhook_event_id: Optional[str] = None,
        reconciliation_attempt_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        policy_result: Optional[str] = None,
        risk_level: Optional[str] = None,
        decision: Optional[str] = None,
        error_code: Optional[str] = None,
        reason: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        request_hash: Optional[str] = None
    ) -> AuditEvent:
        """
        Appends an immutable audit event to the trace.
        Serializes hash-chain writes via row-locked AuditTraceHead.
        """
        trace_id = trace_id or f"trc_{uuid.uuid4().hex[:12]}"
        try:
            # 1. Acquire row lock on the trace head to serialize concurrent writers
            head = db.query(AuditTraceHead).filter(
                AuditTraceHead.merchant_id == merchant_id,
                AuditTraceHead.trace_id == trace_id
            ).with_for_update().first()

            if not head:
                head = AuditTraceHead(
                    merchant_id=merchant_id,
                    trace_id=trace_id,
                    latest_sequence_number=0,
                    latest_event_hash=GENESIS_HASH
                )
                db.add(head)
                db.flush()

            sequence_number = head.latest_sequence_number + 1
            previous_event_hash = head.latest_event_hash
            created_at = datetime.now(timezone.utc).replace(tzinfo=None)
            created_at_iso = created_at.isoformat()

            # 2. Sanitize metadata prior to hashing and persistence
            sanitized_meta = redact_sensitive_data(metadata_json or {})

            # 3. Build canonical payload and calculate SHA-256 hash
            canonical_bytes = AuditIntegrityService.build_canonical_payload(
                merchant_id=merchant_id,
                trace_id=trace_id,
                sequence_number=sequence_number,
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                event_type=event_type,
                tool_name=tool_name,
                resource_type=resource_type,
                resource_id=resource_id,
                previous_state=previous_state,
                new_state=new_state,
                policy_result=policy_result,
                risk_level=risk_level,
                decision=decision,
                status=status,
                error_code=error_code,
                reason=reason,
                metadata_json=sanitized_meta,
                created_at_iso=created_at_iso
            )
            event_hash = AuditIntegrityService.calculate_event_hash(canonical_bytes, previous_event_hash)

            # 4. Create and persist AuditEvent
            event = AuditEvent(
                merchant_id=merchant_id,
                trace_id=trace_id,
                sequence_number=sequence_number,
                session_id=session_id,
                purchase_intent_id=purchase_intent_id,
                order_id=order_id,
                payment_transaction_id=payment_transaction_id,
                payment_attempt_id=payment_attempt_id,
                authorization_id=authorization_id,
                approval_request_id=approval_request_id,
                agent_id=agent_id,
                agent_version=agent_version,
                webhook_event_id=webhook_event_id,
                reconciliation_attempt_id=reconciliation_attempt_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                event_type=event_type,
                tool_name=tool_name,
                resource_type=resource_type,
                resource_id=resource_id,
                previous_state=previous_state,
                new_state=new_state,
                policy_result=policy_result,
                risk_level=risk_level,
                decision=decision,
                status=status,
                error_code=error_code,
                reason=reason,
                metadata_json=sanitized_meta,
                request_hash=request_hash,
                previous_event_hash=previous_event_hash,
                event_hash=event_hash,
                created_at=created_at
            )
            db.add(event)

            # 5. Advance trace head
            head.latest_sequence_number = sequence_number
            head.latest_event_id = event.id
            head.latest_event_hash = event_hash
            db.flush()

            return event

        except Exception as e:
            logger.error(f"AuditService failed to record event for trace {trace_id}: {str(e)}")
            if action in CRITICAL_ACTIONS:
                # Fail-closed for security-critical actions
                raise RuntimeError(f"Audit Persistence Failure on security-critical action '{action}': {str(e)}") from e
            raise

    @staticmethod
    def get_trace_events(
        db: Session,
        trace_id: str,
        merchant_id: str
    ) -> List[AuditEvent]:
        """
        Retrieves all audit events for a trace ordered deterministically by sequence number.
        """
        return db.query(AuditEvent).filter(
            AuditEvent.merchant_id == merchant_id,
            AuditEvent.trace_id == trace_id
        ).order_by(AuditEvent.sequence_number.asc()).all()

    @staticmethod
    def get_trace_summary(
        db: Session,
        trace_id: str,
        merchant_id: str
    ) -> Dict[str, Any]:
        """
        Generates an executive summary of a trace including integrity verification,
        lifecycle stage detection, and timing.
        """
        events = AuditService.get_trace_events(db, trace_id, merchant_id)
        if not events:
            return None

        integrity_res = AuditIntegrityService.verify_trace(db, trace_id, merchant_id)
        
        first_event = events[0]
        last_event = events[-1]
        duration_ms = (last_event.created_at - first_event.created_at).total_seconds() * 1000.0

        # Stage aggregations
        tool_calls = sum(1 for e in events if e.event_type in ("TOOL_CALL", "TOOL_EXECUTION"))
        agents = {e.agent_id for e in events if e.agent_id}
        
        policy_event = next((e for e in events if e.event_type == "POLICY_EVALUATION" or e.policy_result), None)
        approval_event = next((e for e in reversed(events) if e.action in ("APPROVE_REQUEST", "REJECT_REQUEST", "APPROVAL_REQUIRED")), None)
        payment_event = next((e for e in reversed(events) if e.action in ("CREATE_PAYMENT_ORDER", "PROCESS_WEBHOOK", "RECONCILE_PAYMENT") or e.new_state), None)

        return {
            "trace_id": trace_id,
            "merchant_id": merchant_id,
            "event_count": len(events),
            "first_timestamp": first_event.created_at.isoformat(),
            "last_timestamp": last_event.created_at.isoformat(),
            "duration_ms": round(duration_ms, 2),
            "current_status": last_event.status,
            "final_outcome": last_event.action if last_event.status == "SUCCESS" else f"{last_event.action} ({last_event.status})",
            "integrity": {
                "is_valid": integrity_res["is_valid"],
                "tampering_detected": integrity_res["tampering_detected"],
                "detail": integrity_res["detail"]
            },
            "agent_count": len(agents),
            "tool_call_count": tool_calls,
            "policy_decision": policy_event.decision if policy_event else None,
            "risk_level": policy_event.risk_level if policy_event else None,
            "approval_status": approval_event.status if approval_event else "NOT_REQUIRED",
            "payment_status": payment_event.new_state if payment_event else None,
            "events": [
                {
                    "id": e.id,
                    "sequence_number": e.sequence_number,
                    "timestamp": e.created_at.isoformat(),
                    "actor_type": e.actor_type,
                    "actor_id": e.actor_id,
                    "action": e.action,
                    "event_type": e.event_type,
                    "tool_name": e.tool_name,
                    "resource_type": e.resource_type,
                    "resource_id": e.resource_id,
                    "previous_state": e.previous_state,
                    "new_state": e.new_state,
                    "policy_result": e.policy_result,
                    "risk_level": e.risk_level,
                    "decision": e.decision,
                    "status": e.status,
                    "error_code": e.error_code,
                    "reason": e.reason,
                    "metadata": e.metadata_json,
                    "previous_event_hash": e.previous_event_hash,
                    "event_hash": e.event_hash
                }
                for e in events
            ]
        }
