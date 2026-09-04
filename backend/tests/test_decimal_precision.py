import pytest
from decimal import Decimal
from sqlalchemy.orm import Session
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart, CartItem
from app.services.purchase_intent_service import PurchaseIntentService
from app.tools.shopping_tools import add_to_cart

def test_financial_decimal_precision_integrity(db: Session, setup_test_data):
    """
    Test exact decimal arithmetic where binary floating-point fails.
    0.10 + 0.20 in float produces 0.30000000000000004.
    In Decimal/NUMERIC, it MUST produce exactly Decimal('0.30').
    """
    m1_id = setup_test_data["m1"]
    
    # 1. Create two micro-priced items
    p1 = Product(merchant_id=m1_id, name="Micro Item A", price=Decimal("0.10"), category="Digital", is_active=True)
    p2 = Product(merchant_id=m1_id, name="Micro Item B", price=Decimal("0.20"), category="Digital", is_active=True)
    db.add_all([p1, p2])
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=100))
    db.add(Inventory(merchant_id=m1_id, product_id=p2.id, stock_quantity=100))
    db.commit()

    # 2. Add to cart
    session_id = "sess_decimal_exact"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p2.id, quantity=1)

    # 3. Create purchase intent and verify exact Decimal representation
    intent = PurchaseIntentService.create_purchase_intent(
        db=db,
        merchant_id=m1_id,
        session_id=session_id,
        buyer_id="buyer_precision"
    )

    expected = Decimal("0.30")
    assert Decimal(str(intent.requested_amount)) == expected
    assert str(intent.requested_amount) == "0.30"
    # Ensure float drift is completely absent
    assert float(intent.requested_amount) == 0.3
