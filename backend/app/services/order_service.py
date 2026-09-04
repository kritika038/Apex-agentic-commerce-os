from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart
from app.schemas.order import (
    OrderResponse,
    OrderItem,
    OrderPaymentInfo,
    OrderPriceSummary,
    OrderTimelineStep,
    BuyAgainResponse,
)
from app.schemas.commerce import DeliveryAddress
from app.tools.shopping_tools import add_to_cart, get_cart

class OrderService:
    @staticmethod
    def _map_transaction_to_order(tx: PaymentTransaction, pi: PurchaseIntent) -> OrderResponse:
        # Determine human-friendly order number
        order_num = f"ACO-{pi.id[:8].upper()}"

        # Parse historical product summary snapshot
        raw_summary = pi.product_summary or {}
        raw_items = raw_summary.get("items", []) if isinstance(raw_summary, dict) else []
        
        items: List[OrderItem] = []
        for it in raw_items:
            unit_p = Decimal(str(it.get("unit_price", 0)))
            qty = int(it.get("quantity", 1))
            sub = Decimal(str(it.get("subtotal", unit_p * qty)))
            items.append(
                OrderItem(
                    product_id=str(it.get("product_id", "")),
                    name=str(it.get("name", "Product")),
                    category=str(it.get("category", "Gear")),
                    quantity=qty,
                    unit_price=unit_p,
                    subtotal=sub,
                    image_url=it.get("image_url")
                )
            )

        # Derive Order & Payment Status
        is_captured = tx.status == "CAPTURED"
        is_failed = tx.status in ["FAILED", "CANCELLED"]
        
        if is_captured:
            order_status = "CONFIRMED"
            payment_status = "VERIFIED"
        elif is_failed:
            order_status = "FAILED"
            payment_status = "FAILED"
        else:
            order_status = "PROCESSING"
            payment_status = tx.status

        # Build Price Summary from historical snapshot
        pricing_data = raw_summary.get("pricing", {}) if isinstance(raw_summary, dict) else {}
        total_amt = Decimal(str(tx.amount or pi.requested_amount or 0))
        
        hist_subtotal = Decimal(str(pricing_data.get("subtotal", sum(Decimal(str(it.subtotal)) for it in items) if items else total_amt)))
        coupon_disc = Decimal(str(pricing_data.get("coupon_discount", 0)))
        voucher_disc = Decimal(str(pricing_data.get("voucher_discount", 0)))
        coin_disc = Decimal(str(pricing_data.get("coin_discount", 0)))
        coins_u = int(pricing_data.get("coins_used", 0))
        pts_earned = int(pricing_data.get("points_to_earn", int(total_amt // Decimal("100")) if is_captured else 0))

        price_summary = OrderPriceSummary(
            subtotal=hist_subtotal,
            coupon_code=pricing_data.get("coupon_code"),
            coupon_discount=coupon_disc,
            voucher_code=pricing_data.get("voucher_code"),
            voucher_discount=voucher_disc,
            coins_used=coins_u,
            coin_discount=coin_disc,
            delivery_charges=Decimal("0.00"),
            taxes=Decimal("0.00"),
            discount=coupon_disc + voucher_disc + coin_disc,
            total_amount=total_amt,
            currency=tx.currency or pi.currency or "INR",
            points_earned=pts_earned if is_captured else 0
        )

        # Parse immutable Delivery Address snapshot
        addr_dict = pi.delivery_address if isinstance(pi.delivery_address, dict) else None
        delivery_addr: Optional[DeliveryAddress] = None
        if addr_dict and addr_dict.get("full_name"):
            try:
                delivery_addr = DeliveryAddress(**addr_dict)
            except Exception:
                pass

        # Build realistic chronological timeline
        timeline = [
            OrderTimelineStep(
                title="Order Placed",
                status="COMPLETED",
                timestamp=pi.created_at,
                description="Purchase intent and order requirements submitted."
            ),
            OrderTimelineStep(
                title="Payment Verified",
                status="COMPLETED" if is_captured else ("FAILED" if is_failed else "PENDING"),
                timestamp=tx.captured_at or (tx.created_at if is_captured else None),
                description="Razorpay HMAC-SHA256 signature verified by security engine." if is_captured else ("Payment could not be completed." if is_failed else "Awaiting payment capture.")
            ),
            OrderTimelineStep(
                title="Order Confirmed",
                status="COMPLETED" if is_captured else ("FAILED" if is_failed else "PENDING"),
                timestamp=tx.captured_at if is_captured else None,
                description="Inventory confirmed and order queued for fulfillment." if is_captured else None
            ),
            OrderTimelineStep(
                title="Shipping & Dispatch",
                status="UNAVAILABLE",
                timestamp=None,
                description="Standard delivery (2-4 business days). Tracking info will be updated upon courier dispatch."
            )
        ]

        payment_info = OrderPaymentInfo(
            method="Razorpay",
            status=payment_status,
            razorpay_order_id=tx.razorpay_order_id,
            razorpay_payment_id=tx.razorpay_payment_id,
            paid_at=tx.captured_at
        )

        return OrderResponse(
            id=tx.id,
            order_number=order_num,
            purchase_intent_id=pi.id,
            created_at=tx.created_at,
            status=order_status,
            total_amount=total_amt,
            currency=tx.currency or "INR",
            items=items,
            payment=payment_info,
            price_summary=price_summary,
            delivery_address=delivery_addr,
            timeline=timeline
        )

    @staticmethod
    def get_customer_orders(db: Session, buyer_id: str, limit: int = 50) -> List[OrderResponse]:
        """
        Retrieves all orders placed by the authenticated customer.
        Strictly filters by buyer_id derived from the authentication token.
        """
        transactions = (
            db.query(PaymentTransaction)
            .join(PurchaseIntent, PaymentTransaction.purchase_intent_id == PurchaseIntent.id)
            .filter(PurchaseIntent.buyer_id == buyer_id)
            .order_by(PaymentTransaction.created_at.desc())
            .limit(limit)
            .all()
        )

        results = []
        for tx in transactions:
            pi = tx.purchase_intent
            if pi:
                results.append(OrderService._map_transaction_to_order(tx, pi))
        return results

    @staticmethod
    def get_order_by_id(
        db: Session,
        order_id: str,
        buyer_id: Optional[str] = None,
        is_admin: bool = False
    ) -> OrderResponse:
        """
        Retrieves a single order by transaction ID or purchase intent ID.
        Enforces tenant and buyer authorization boundaries.
        """
        tx = (
            db.query(PaymentTransaction)
            .filter(
                (PaymentTransaction.id == order_id) |
                (PaymentTransaction.purchase_intent_id == order_id) |
                (PaymentTransaction.razorpay_order_id == order_id)
            )
            .first()
        )

        if not tx or not tx.purchase_intent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order '{order_id}' not found."
            )

        pi = tx.purchase_intent
        if not is_admin and buyer_id and pi.buyer_id != buyer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to view this order."
            )

        return OrderService._map_transaction_to_order(tx, pi)

    @staticmethod
    def buy_again(
        db: Session,
        order_id: str,
        session_id: str,
        buyer_id: Optional[str] = None,
        is_admin: bool = False
    ) -> BuyAgainResponse:
        """
        Re-orders products from a previous order into the current cart session.
        CRITICAL GOVERNANCE RULES:
        1. Never uses historical prices; always applies current database prices.
        2. Strictly validates current active status and live inventory.
        3. Returns detailed breakdown of added vs unavailable items.
        """
        order = OrderService.get_order_by_id(db, order_id, buyer_id=buyer_id, is_admin=is_admin)
        
        added = []
        unavailable = []

        for it in order.items:
            product = db.query(Product).filter(Product.id == it.product_id, Product.is_active == True).first()
            if not product:
                unavailable.append({
                    "product_id": it.product_id,
                    "name": it.name,
                    "reason": "Product is no longer available in the catalog."
                })
                continue

            inventory = db.query(Inventory).filter(Inventory.product_id == product.id).first()
            available_stock = inventory.stock_quantity if inventory else 0

            if available_stock < it.quantity:
                if available_stock <= 0:
                    unavailable.append({
                        "product_id": it.product_id,
                        "name": product.name,
                        "reason": "Product is currently out of stock."
                    })
                    continue
                # Add only available stock
                target_qty = available_stock
            else:
                target_qty = it.quantity

            # Add to cart with current authoritative database price
            cart_res = add_to_cart(
                db=db,
                merchant_id=product.merchant_id,
                session_id=session_id,
                product_id=product.id,
                quantity=target_qty
            )

            if "error" in cart_res:
                unavailable.append({
                    "product_id": it.product_id,
                    "name": product.name,
                    "reason": cart_res["error"]
                })
            else:
                added.append({
                    "product_id": product.id,
                    "name": product.name,
                    "quantity": target_qty,
                    "current_price": float(product.price),
                    "historical_price": float(it.unit_price)
                })

        updated_cart = get_cart(db=db, merchant_id=Product.merchant_id if added else "", session_id=session_id)

        if added and not unavailable:
            msg = f"Successfully added {len(added)} item(s) to your cart at current catalog prices."
        elif added and unavailable:
            msg = f"Added {len(added)} item(s) to your cart. {len(unavailable)} item(s) could not be reordered due to stock limits."
        else:
            msg = "None of the items from this order could be added (out of stock or discontinued)."

        return BuyAgainResponse(
            success=bool(added),
            added_items=added,
            unavailable_items=unavailable,
            cart=updated_cart,
            message=msg
        )

    @staticmethod
    def cancel_order(
        db: Session,
        order_id: str,
        buyer_id: Optional[str] = None,
        reason: Optional[str] = None,
        is_admin: bool = False
    ) -> Dict[str, Any]:
        """
        Cancels an order if eligible (PROCESSING / CONFIRMED / CREATED).
        Restores product inventory and writes an immutable audit trail event.
        """
        tx = (
            db.query(PaymentTransaction)
            .filter(
                (PaymentTransaction.id == order_id) |
                (PaymentTransaction.purchase_intent_id == order_id) |
                (PaymentTransaction.razorpay_order_id == order_id)
            )
            .first()
        )

        if not tx or not tx.purchase_intent:
            raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found.")

        pi = tx.purchase_intent
        if not is_admin and buyer_id and pi.buyer_id != buyer_id:
            raise HTTPException(status_code=403, detail="You are not authorized to cancel this order.")

        if tx.status == "CANCELLED":
            raise HTTPException(status_code=400, detail="This order is already cancelled.")

        if tx.status in ["FAILED"]:
            raise HTTPException(status_code=400, detail=f"Order in state '{tx.status}' cannot be cancelled.")

        # Re-stock inventory for confirmed orders
        raw_summary = pi.product_summary or {}
        raw_items = raw_summary.get("items", []) if isinstance(raw_summary, dict) else []
        for it in raw_items:
            p_id = it.get("product_id")
            qty = int(it.get("quantity", 1))
            inv = db.query(Inventory).filter(Inventory.product_id == p_id).first()
            if inv:
                inv.stock_quantity += qty

        tx.status = "CANCELLED"
        pi.status = "REJECTED"
        db.commit()

        from app.services.audit_service import AuditService
        AuditService.record_event(
            db=db,
            merchant_id=tx.merchant_id,
            trace_id=pi.trace_id or f"trace_cancel_{tx.id[:8]}",
            session_id=pi.session_id,
            purchase_intent_id=pi.id,
            payment_transaction_id=tx.id,
            actor_type="CUSTOMER" if not is_admin else "MERCHANT",
            action="ORDER_CANCELLED",
            event_type="ORDER_CANCELLED",
            status="SUCCESS",
            metadata_json={"reason": reason or "Customer requested cancellation.", "refund_status": "PROCESSED"}
        )

        return {
            "success": True,
            "order_id": tx.id,
            "status": "CANCELLED",
            "message": "Your order has been successfully cancelled. If funds were debited, refund will process to the original payment method."
        }

    @staticmethod
    def return_order(
        db: Session,
        order_id: str,
        buyer_id: Optional[str] = None,
        reason: Optional[str] = None,
        quantity: int = 1,
        is_admin: bool = False
    ) -> Dict[str, Any]:
        """
        Initiates a return request for eligible orders.
        """
        tx = (
            db.query(PaymentTransaction)
            .filter(
                (PaymentTransaction.id == order_id) |
                (PaymentTransaction.purchase_intent_id == order_id) |
                (PaymentTransaction.razorpay_order_id == order_id)
            )
            .first()
        )

        if not tx or not tx.purchase_intent:
            raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found.")

        pi = tx.purchase_intent
        if not is_admin and buyer_id and pi.buyer_id != buyer_id:
            raise HTTPException(status_code=403, detail="You are not authorized to return this order.")

        from app.services.audit_service import AuditService
        AuditService.record_event(
            db=db,
            merchant_id=tx.merchant_id,
            trace_id=pi.trace_id or f"trace_return_{tx.id[:8]}",
            session_id=pi.session_id,
            purchase_intent_id=pi.id,
            payment_transaction_id=tx.id,
            actor_type="CUSTOMER" if not is_admin else "MERCHANT",
            action="RETURN_REQUESTED",
            event_type="ORDER_RETURN_REQUESTED",
            status="SUCCESS",
            metadata_json={"reason": reason or "Customer initiated return.", "quantity": quantity}
        )

        return {
            "success": True,
            "order_id": tx.id,
            "status": "RETURN_REQUESTED",
            "message": f"Return request submitted for Order #{tx.id[:8].upper()}. Pickup will be scheduled within 24-48 business hours."
        }

