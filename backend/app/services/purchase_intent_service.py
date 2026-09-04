import re
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.database.models.user import User
from app.database.models.cart import Cart, CartItem
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.purchase_intent import PurchaseIntent
from app.schemas.commerce import BuyerConstraints, PurchaseIntentResponse, PurchaseIntentItem, DeliveryAddress

class PurchaseIntentService:
    @staticmethod
    def create_purchase_intent(
        db: Session,
        merchant_id: str,
        session_id: str,
        buyer_id: str,
        constraints: Optional[BuyerConstraints] = None,
        delivery_address: Optional[Any] = None,
        coupon_code: Optional[str] = None,
        voucher_code: Optional[str] = None,
        use_coins: bool = False,
        coins_to_redeem: Optional[int] = None,
        trace_id: Optional[str] = None
    ) -> PurchaseIntent:
        """
        Creates a structured, server-validated Purchase Intent from an authoritative cart.
        
        Boundary:
        - Calculates total purely server-side from DB records using Decimal and PricingService.
        - Validates merchant ownership, active product status, inventory, coupons, vouchers, coins, and buyer constraints.
        - Sets initial status to CREATED with a 15-minute expiration.
        - NO payment orders, payment charges, or authorizations occur here.
        """
        # 1. Retrieve authoritative cart
        cart = db.query(Cart).filter(
            Cart.session_id == session_id,
            Cart.merchant_id == merchant_id
        ).first()
        
        if not cart or not cart.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cart is empty or does not exist for this session."
            )

        # 2. Verify all products and inventory in cart
        items_summary: List[Dict[str, Any]] = []
        calculated_subtotal = Decimal("0.00")

        for item in cart.items:
            product = db.query(Product).filter(
                Product.id == item.product_id,
                Product.merchant_id == merchant_id
            ).first()
            
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product {item.product_id} does not belong to merchant or does not exist."
                )
                
            if not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product '{product.name}' is no longer active."
                )

            inventory = db.query(Inventory).filter(
                Inventory.product_id == product.id,
                Inventory.merchant_id == merchant_id
            ).first()
            
            if not inventory or inventory.stock_quantity < item.quantity:
                available_stock = inventory.stock_quantity if inventory else 0
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient inventory for '{product.name}'. Requested: {item.quantity}, Available: {available_stock}."
                )

            # Server-authoritative unit price as Decimal
            unit_price = Decimal(str(product.price))
            subtotal = unit_price * Decimal(str(item.quantity))
            calculated_subtotal += subtotal

            items_summary.append({
                "product_id": product.id,
                "name": product.name,
                "quantity": item.quantity,
                "unit_price": str(unit_price),
                "subtotal": str(subtotal),
                "category": product.category,
                "image_url": product.attributes.get("image_url") if isinstance(product.attributes, dict) else None
            })

        # 3. Currency validation
        currency = cart.currency or "INR"
        req_currency = constraints.currency if isinstance(constraints, BuyerConstraints) else (constraints.get("currency") if isinstance(constraints, dict) else None)
        if req_currency and req_currency != currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested currency '{req_currency}' does not match merchant currency '{currency}'."
            )

        # 4. Authoritative Pricing & Discount Calculation
        from app.services.pricing_service import PricingService
        user = db.query(User).filter((User.email == buyer_id) | (User.id == buyer_id)).first()
        pricing_res = PricingService.calculate_authoritative_pricing(
            db=db,
            merchant_id=merchant_id,
            session_id=session_id,
            user=user,
            coupon_code=coupon_code,
            voucher_code=voucher_code,
            use_coins=use_coins,
            requested_coins=coins_to_redeem
        )
        final_payable_total = pricing_res.total

        # 5. Buyer constraints validation (e.g. max_price budget against final total)
        max_p_val = constraints.max_price if isinstance(constraints, BuyerConstraints) else (constraints.get("max_price") if isinstance(constraints, dict) else None)
        if max_p_val is not None:
            max_p = Decimal(str(max_p_val))
            if final_payable_total > max_p:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Payable total (₹{final_payable_total:,.2f}) exceeds buyer budget constraint of ₹{max_p:,.2f}."
                )

        # Update cart total deterministically
        cart.total_amount = final_payable_total

        # 6. Delivery address validation and snapshot sanitization
        address_dict = {}
        if delivery_address:
            if isinstance(delivery_address, DeliveryAddress):
                addr_data = delivery_address.model_dump()
            elif isinstance(delivery_address, dict):
                addr_data = delivery_address
            else:
                addr_data = {}

            full_name = str(addr_data.get("full_name") or "").strip()
            phone = re.sub(r"\D", "", str(addr_data.get("phone") or ""))
            email = str(addr_data.get("email") or "").strip()
            address_line1 = str(addr_data.get("address_line1") or "").strip()
            address_line2 = str(addr_data.get("address_line2") or "").strip() or None
            landmark = str(addr_data.get("landmark") or "").strip() or None
            city = str(addr_data.get("city") or "").strip()
            state_val = str(addr_data.get("state") or "").strip()
            pin_code = re.sub(r"\D", "", str(addr_data.get("pin_code") or ""))
            country = str(addr_data.get("country") or "India").strip()

            if full_name or address_line1 or pin_code:
                if len(full_name) < 2:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Full name must be at least 2 characters.")
                if len(phone) != 10:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mobile number must be 10 digits.")
                if not email or "@" not in email or "." not in email:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter a valid email address.")
                if len(address_line1) < 3:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter a valid delivery address.")
                if len(city) < 2:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter a valid city name.")
                if len(state_val) < 2:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please select a valid state.")
                if len(pin_code) != 6:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PIN code must be 6 digits.")

                address_dict = {
                    "full_name": full_name,
                    "phone": phone,
                    "email": email,
                    "address_line1": address_line1,
                    "address_line2": address_line2,
                    "landmark": landmark,
                    "city": city,
                    "state": state_val,
                    "pin_code": pin_code,
                    "country": country
                }

        # 7. Set 15-minute expiration
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at = now + timedelta(minutes=15)

        # 8. Create PurchaseIntent with status CREATED and pricing snapshot
        constraints_dict = {}
        if constraints:
            if isinstance(constraints, BuyerConstraints):
                constraints_dict = constraints.model_dump()
            elif isinstance(constraints, dict):
                constraints_dict = constraints
            if constraints_dict.get("max_price") is not None:
                constraints_dict["max_price"] = str(constraints_dict["max_price"])

        pricing_snapshot = {
            "subtotal": str(pricing_res.subtotal),
            "coupon_code": pricing_res.coupon_code,
            "coupon_discount": str(pricing_res.coupon_discount),
            "voucher_code": pricing_res.voucher_code,
            "voucher_discount": str(pricing_res.voucher_discount),
            "coins_used": pricing_res.coins_used,
            "coin_discount": str(pricing_res.coin_discount),
            "delivery_charges": str(pricing_res.delivery_charges),
            "taxes": str(pricing_res.taxes),
            "total": str(pricing_res.total),
            "points_to_earn": pricing_res.points_to_earn
        }

        purchase_intent = PurchaseIntent(
            merchant_id=merchant_id,
            buyer_id=buyer_id,
            session_id=session_id,
            cart_id=cart.id,
            status="CREATED",
            currency=currency,
            requested_amount=final_payable_total,
            product_summary={
                "items": items_summary,
                "pricing": pricing_snapshot
            },
            constraints=constraints_dict,
            delivery_address=address_dict,
            trace_id=trace_id or f"pi_trace_{uuid.uuid4().hex[:12]}",
            expires_at=expires_at
        )

        db.add(purchase_intent)
        db.flush()

        from app.services.audit_service import AuditService
        AuditService.record_event(
            db=db,
            merchant_id=merchant_id,
            trace_id=purchase_intent.trace_id,
            session_id=session_id,
            purchase_intent_id=purchase_intent.id,
            actor_type="USER",
            actor_id=buyer_id,
            action="CREATE_PURCHASE_INTENT",
            event_type="PURCHASE_INTENT_CREATED",
            resource_type="PURCHASE_INTENT",
            resource_id=purchase_intent.id,
            new_state="CREATED",
            status="SUCCESS",
            metadata_json={
                "requested_amount": str(final_payable_total),
                "currency": currency,
                "pricing": pricing_snapshot,
                "item_count": len(items_summary),
                "items": items_summary
            }
        )

        db.commit()
        db.refresh(purchase_intent)
        return purchase_intent

    @staticmethod
    def get_purchase_intent_with_expiration(
        db: Session,
        intent_id: str,
        merchant_id: Optional[str] = None
    ) -> PurchaseIntent:
        """
        Retrieves a purchase intent by ID and evaluates expiration.
        If current time exceeds expires_at and status is CREATED/VALIDATED, transitions to EXPIRED.
        """
        query = db.query(PurchaseIntent).filter(PurchaseIntent.id == intent_id)
        if merchant_id:
            query = query.filter(PurchaseIntent.merchant_id == merchant_id)
            
        intent = query.first()
        if not intent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase intent not found."
            )

        # Auto-expire if past expiration time
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if intent.expires_at and now > intent.expires_at and intent.status in ("CREATED", "DRAFT", "VALIDATED"):
            intent.status = "EXPIRED"
            db.commit()
            db.refresh(intent)

        return intent

    @staticmethod
    def format_response(intent: PurchaseIntent) -> PurchaseIntentResponse:
        raw_items = intent.product_summary.get("items", []) if intent.product_summary else []
        items = []
        for it in raw_items:
            items.append(PurchaseIntentItem(
                product_id=it.get("product_id", "unknown_prod"),
                name=it.get("name") or it.get("product_name", "Product"),
                quantity=int(it.get("quantity", 1)),
                unit_price=Decimal(str(it.get("unit_price", 0))),
                subtotal=Decimal(str(it.get("subtotal", 0)))
            ))
        
        return PurchaseIntentResponse(
            id=intent.id,
            status=intent.status,
            merchant_id=intent.merchant_id,
            buyer_id=intent.buyer_id,
            cart_id=intent.cart_id,
            currency=intent.currency,
            requested_amount=Decimal(str(intent.requested_amount)),
            items=items,
            delivery_address=intent.delivery_address or None,
            constraints=intent.constraints or {},
            trace_id=intent.trace_id,
            expires_at=intent.expires_at,
            created_at=intent.created_at
        )
