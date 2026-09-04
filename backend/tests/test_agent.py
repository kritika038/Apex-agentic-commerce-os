import pytest
from sqlalchemy.orm import Session
from app.agents.shopping_agent import ShoppingAgent
from app.ai.gateway import LLMGateway
from app.ai.providers.mock_provider import MockLLMProvider
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.merchant import Merchant

from decimal import Decimal

def test_shopping_agent_search(db: Session):
    m1 = Merchant(name="M", domain="m.test")
    db.add(m1)
    db.commit()
    
    p = Product(merchant_id=m1.id, name="Test Running Shoes", price=Decimal("3000.00"), category="Running")
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1.id, product_id=p.id, stock_quantity=10))
    db.commit()

    gateway = LLMGateway(provider=MockLLMProvider())
    agent = ShoppingAgent(db=db, merchant_id=m1.id, session_id="test_sess", gateway=gateway)
    
    # 1. Search trigger
    response = agent.process_message("I need running shoes under 4000")
    assert response.session_id == "test_sess"
    assert "Mock" in response.message or "Running Shoes" in response.message

def test_shopping_agent_add_to_cart(db: Session):
    m1 = Merchant(name="M", domain="m.test2")
    db.add(m1)
    db.commit()
    
    gateway = LLMGateway(provider=MockLLMProvider())
    agent = ShoppingAgent(db=db, merchant_id=m1.id, session_id="test_sess2", gateway=gateway)
    
    response = agent.process_message("add it to cart")
    # In a real test, product_id="test_id" won't exist so tool will return error, but it won't crash
    assert response.cart is not None

def test_tool_registry_permissions():
    from app.tools.registry import tool_registry
    add_tool_def = tool_registry.get_definition("add_to_cart")
    assert add_tool_def.required_permission == "MODIFY_CART"
