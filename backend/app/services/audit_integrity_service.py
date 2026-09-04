import json
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from app.database.models.audit_event import AuditEvent
from app.utils.redaction import redact_sensitive_data

GENESIS_HASH = "0" * 64

class AuditIntegrityService:
    """
    Cryptographic verification service for tamper-evident hash chains.
    Verifies that all audit events for a trace form a strictly monotonic,
    unbroken, un-forked SHA-256 chain.
    """

    @staticmethod
    def build_canonical_payload(
        merchant_id: str,
        trace_id: str,
        sequence_number: int,
        actor_type: str,
        actor_id: Optional[str],
        action: str,
        event_type: str,
        tool_name: Optional[str],
        resource_type: Optional[str],
        resource_id: Optional[str],
        previous_state: Optional[str],
        new_state: Optional[str],
        policy_result: Optional[str],
        risk_level: Optional[str],
        decision: Optional[str],
        status: str,
        error_code: Optional[str],
        reason: Optional[str],
        metadata_json: Dict[str, Any],
        created_at_iso: str
    ) -> bytes:
        """
        Generates deterministic UTF-8 bytes for the canonical payload.
        Redacts sensitive data prior to payload construction and hashing.
        """
        sanitized_meta = redact_sensitive_data(metadata_json or {})
        
        canonical_dict = {
            "action": str(action),
            "actor_id": str(actor_id) if actor_id else None,
            "actor_type": str(actor_type),
            "created_at": str(created_at_iso),
            "decision": str(decision) if decision else None,
            "error_code": str(error_code) if error_code else None,
            "event_type": str(event_type),
            "merchant_id": str(merchant_id),
            "metadata_json": sanitized_meta,
            "new_state": str(new_state) if new_state else None,
            "policy_result": str(policy_result) if policy_result else None,
            "previous_state": str(previous_state) if previous_state else None,
            "reason": str(reason) if reason else None,
            "resource_id": str(resource_id) if resource_id else None,
            "resource_type": str(resource_type) if resource_type else None,
            "risk_level": str(risk_level) if risk_level else None,
            "sequence_number": int(sequence_number),
            "status": str(status),
            "tool_name": str(tool_name) if tool_name else None,
            "trace_id": str(trace_id)
        }

        # Deterministic sorting, standard separators, UTF-8 encoded
        return json.dumps(canonical_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def calculate_event_hash(canonical_payload: bytes, previous_event_hash: str) -> str:
        """
        event_hash = SHA256(canonical_payload + previous_event_hash)
        """
        combined = canonical_payload + previous_event_hash.encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    @staticmethod
    def verify_trace(db: Session, trace_id: str, merchant_id: str) -> Dict[str, Any]:
        """
        Verifies the complete cryptographic hash chain for a specific (merchant_id, trace_id).
        Detects:
        - Payload modification
        - Event deletion / gaps
        - Event insertion / duplicate sequence
        - Event reordering
        - Chain forks
        """
        events = db.query(AuditEvent).filter(
            AuditEvent.merchant_id == merchant_id,
            AuditEvent.trace_id == trace_id
        ).order_by(AuditEvent.sequence_number.asc()).all()

        if not events:
            return {
                "is_valid": True,
                "event_count": 0,
                "first_invalid_event_id": None,
                "tampering_detected": False,
                "detail": "No audit events found for trace."
            }

        expected_previous_hash = GENESIS_HASH
        seen_sequences = set()

        for idx, event in enumerate(events):
            expected_seq = idx + 1

            # 1. Check Sequence Number strictly monotonic (no gaps, no duplicates, no reordering)
            if event.sequence_number in seen_sequences:
                return {
                    "is_valid": False,
                    "event_count": len(events),
                    "first_invalid_event_id": event.id,
                    "tampering_detected": True,
                    "detail": f"Duplicate sequence number detected: {event.sequence_number}"
                }
            seen_sequences.add(event.sequence_number)

            if event.sequence_number != expected_seq:
                return {
                    "is_valid": False,
                    "event_count": len(events),
                    "first_invalid_event_id": event.id,
                    "tampering_detected": True,
                    "detail": f"Sequence gap or reordering detected. Expected sequence {expected_seq}, found {event.sequence_number}"
                }

            # 2. Check previous_event_hash linkage
            if event.previous_event_hash != expected_previous_hash:
                return {
                    "is_valid": False,
                    "event_count": len(events),
                    "first_invalid_event_id": event.id,
                    "tampering_detected": True,
                    "detail": f"Broken hash chain at sequence {event.sequence_number}. Expected previous hash {expected_previous_hash}, found {event.previous_event_hash}"
                }

            # 3. Recompute canonical payload and event_hash
            created_at_iso = event.created_at.isoformat()
            canonical_bytes = AuditIntegrityService.build_canonical_payload(
                merchant_id=event.merchant_id,
                trace_id=event.trace_id,
                sequence_number=event.sequence_number,
                actor_type=event.actor_type,
                actor_id=event.actor_id,
                action=event.action,
                event_type=event.event_type,
                tool_name=event.tool_name,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                previous_state=event.previous_state,
                new_state=event.new_state,
                policy_result=event.policy_result,
                risk_level=event.risk_level,
                decision=event.decision,
                status=event.status,
                error_code=event.error_code,
                reason=event.reason,
                metadata_json=event.metadata_json,
                created_at_iso=created_at_iso
            )
            recomputed_hash = AuditIntegrityService.calculate_event_hash(canonical_bytes, event.previous_event_hash)

            if recomputed_hash != event.event_hash:
                return {
                    "is_valid": False,
                    "event_count": len(events),
                    "first_invalid_event_id": event.id,
                    "tampering_detected": True,
                    "detail": f"Payload modification detected at sequence {event.sequence_number}. Expected hash {recomputed_hash}, found {event.event_hash}"
                }

            # Advance expected previous hash for next iteration
            expected_previous_hash = event.event_hash

        return {
            "is_valid": True,
            "event_count": len(events),
            "first_invalid_event_id": None,
            "tampering_detected": False,
            "detail": f"Tamper-evident hash chain verified successfully across {len(events)} events."
        }
