import json
from fastapi import APIRouter, Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.payments.service import PaymentService

router = APIRouter(tags=["Webhooks"])

@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Razorpay Webhook Handler.
    Verifies HMAC-SHA256 signature using RAW request body bytes and deduplicates events via x-razorpay-event-id.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature") or request.headers.get("x-razorpay-signature") or ""
    event_id = request.headers.get("X-Razorpay-Event-Id") or request.headers.get("x-razorpay-event-id")

    if not event_id:
        try:
            parsed = json.loads(raw_body.decode("utf-8"))
            event_id = parsed.get("event_id") or parsed.get("id")
        except Exception:
            event_id = None

    if not event_id:
        event_id = f"ev_fallback_{hash(raw_body)}"

    is_valid, msg, webhook_ev = PaymentService.process_webhook_event(
        db=db,
        raw_body=raw_body,
        signature=signature,
        event_id=event_id
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Webhook verification failed: {msg}"
        )

    return {
        "status": "ok",
        "message": msg,
        "event_id": event_id,
        "processing_status": webhook_ev.processing_status if webhook_ev else "UNKNOWN"
    }
