import sys
import os
from decimal import Decimal
from datetime import datetime, timezone, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import SessionLocal, engine
from app.database.models.base import Base
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.agent import Agent, Permission, AgentPermission
from app.database.models.policy import Policy
from app.database.models.external_store import ExternalStore
from app.database.models.external_offer import ExternalProductOffer, PriceObservationHistory
from app.database.seeds.marketplace_catalog import generate_marketplace_products
from app.services.external_stores.registry import ExternalStoreRegistry
from app.core.security import get_password_hash

def seed_db(reset: bool = True):
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # 1. Create Merchant
    merchant = Merchant(
        name="Apex Sports Merchant",
        domain="demo-sports.test"
    )
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    
    # 2. Create Users (Merchant Admin & Customer)
    admin_user = User(
        email="admin@demo-sports.test",
        hashed_password=get_password_hash("password123"),
        full_name="Merchant Admin",
        merchant_id=merchant.id,
        role="merchant_admin"
    )
    customer_user = User(
        email="customer@demo-sports.test",
        hashed_password=get_password_hash("password123"),
        full_name="Alex Customer",
        merchant_id=merchant.id,
        role="customer"
    )
    db.add_all([admin_user, customer_user])
    db.commit()
    db.refresh(admin_user)
    
    # 3. Create External Stores Registry
    stores_data = [
        {"name": "Amazon India", "domain": "amazon.in", "store_type": "MARKETPLACE", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/a/a9/Amazon_logo.svg", "status": "DEMO_VERIFIED"},
        {"name": "Flipkart", "domain": "flipkart.com", "store_type": "MARKETPLACE", "logo_url": "https://static-assets-web.flixcart.com/batman-returns/batman-returns/p/images/fkheaderlogo_exploreplus-448884.svg", "status": "DEMO_VERIFIED"},
        {"name": "Myntra", "domain": "myntra.com", "store_type": "MARKETPLACE", "logo_url": "https://constant.myntassets.com/web/assets/img/icon.5d108c858a0db793700f0be5d3ad1e120e01a500.png", "status": "DEMO_VERIFIED"},
        {"name": "Nike Official", "domain": "nike.com", "store_type": "OFFICIAL_BRAND", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/a/a6/Logo_NIKE.svg", "status": "OFFICIAL_LINK_ONLY"},
        {"name": "Adidas Official", "domain": "adidas.co.in", "store_type": "OFFICIAL_BRAND", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/2/20/Adidas_Logo.svg", "status": "OFFICIAL_LINK_ONLY"},
        {"name": "Puma Official", "domain": "puma.com", "store_type": "OFFICIAL_BRAND", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/8/88/Puma_logo.svg", "status": "OFFICIAL_LINK_ONLY"},
        {"name": "Decathlon", "domain": "decathlon.in", "store_type": "RETAILER", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/0/08/Decathlon_Logo.png", "status": "OFFICIAL_LINK_ONLY"},
        {"name": "Croma", "domain": "croma.com", "store_type": "RETAILER", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/3/3b/Croma_Logo.png", "status": "DEMO_VERIFIED"},
        {"name": "Sony Official", "domain": "sony.co.in", "store_type": "OFFICIAL_BRAND", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/c/ca/Sony_logo.svg", "status": "OFFICIAL_LINK_ONLY"},
        {"name": "Apple Official", "domain": "apple.com", "store_type": "OFFICIAL_BRAND", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg", "status": "OFFICIAL_LINK_ONLY"},
        {"name": "boAt Lifestyle", "domain": "boat-lifestyle.com", "store_type": "OFFICIAL_BRAND", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/d/d4/Boat_logo.svg", "status": "OFFICIAL_LINK_ONLY"},
        {"name": "Noise Official", "domain": "gonoise.com", "store_type": "OFFICIAL_BRAND", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/e/e0/Noise_Logo.png", "status": "OFFICIAL_LINK_ONLY"}
    ]

    store_map: dict[str, ExternalStore] = {}
    for s_info in stores_data:
        store = ExternalStore(
            name=s_info["name"],
            domain=s_info["domain"],
            store_type=s_info["store_type"],
            logo_url=s_info["logo_url"],
            status=s_info["status"],
            enabled=True,
            verified=True,
            supports_product_links=True
        )
        db.add(store)
        db.flush()
        store_map[s_info["domain"]] = store

    # 4. Create Marketplace Products & Verified External Offers
    products_catalog = generate_marketplace_products()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    for p_info in products_catalog:
        p = Product(
            merchant_id=merchant.id,
            name=p_info["name"],
            description=p_info["description"],
            brand=p_info.get("brand"),
            category=p_info["category"],
            subcategory=p_info.get("subcategory"),
            price=p_info["price"],
            mrp=p_info.get("mrp"),
            currency=p_info.get("currency", "INR"),
            gtin=p_info.get("gtin"),
            model_number=p_info.get("model_number"),
            sku=p_info.get("sku"),
            image_url=p_info.get("image_url"),
            image_urls=[p_info.get("image_url")] if p_info.get("image_url") else [],
            rating=p_info.get("rating", 4.5),
            review_count=p_info.get("review_count", 0),
            tags=p_info.get("tags", []),
            variant_group_id=p_info.get("variant_group_id"),
            attributes=p_info.get("attributes") or {"image_url": p_info.get("image_url")},
            is_active=True,
            external_comparison_enabled=True
        )
        db.add(p)
        db.flush()
        
        # Add inventory
        inv = Inventory(merchant_id=merchant.id, product_id=p.id, stock_quantity=p_info.get("stock", 50))
        db.add(inv)
        
        # Add external offers
        for off_data in p_info.get("external_offers", []):
            store = store_map.get(off_data["store_domain"])
            if store:
                ext_pid = off_data.get("asin") or off_data.get("fsn") or off_data.get("style_id")
                ext_url = off_data.get("external_url")
                if not ext_url:
                    connector = ExternalStoreRegistry.get_connector(store.domain)
                    ext_url = connector.build_product_url(ext_pid or "", p_info["name"]) if connector else f"https://www.{store.domain}/s?k={p_info['name'].replace(' ', '+')}"

                is_search = "/s?k=" in ext_url or "/search" in ext_url or off_data.get("match_type") == "SEARCH_FALLBACK"
                match_type = "SEARCH_FALLBACK" if is_search else off_data.get("match_type", "EXACT_PRODUCT")
                price_val = off_data.get("price") if not is_search else None
                mrp_val = off_data.get("mrp") if not is_search else None

                offer = ExternalProductOffer(
                    apex_product_id=p.id,
                    external_store_id=store.id,
                    external_product_id=ext_pid if not is_search else None,
                    external_product_title=off_data.get("external_title") or f"{p_info['name']} on {store.name}",
                    external_url=ext_url,
                    image_url=off_data.get("image_url") if not is_search else None,
                    price=price_val,
                    mrp=mrp_val,
                    currency="INR",
                    availability="IN_STOCK",
                    match_type=match_type,
                    match_confidence=off_data.get("confidence", 0.99 if not is_search else 0.60),
                    match_reason=off_data.get("reason", "Verified listing match" if not is_search else "Search query fallback"),
                    source_status="VERIFIED",
                    source_verified=True,
                    observed_at=now,
                    attributes_json={"identity": off_data.get("identity")} if off_data.get("identity") else {}
                )
                db.add(offer)

                # Seed historical observations only for verified exact offers with price
                if price_val:
                    for days_ago, p_mult in [(7, Decimal("1.02")), (30, Decimal("1.05")), (90, Decimal("1.08"))]:
                        hist = PriceObservationHistory(
                            apex_product_id=p.id,
                            external_store_id=store.id,
                            price=round(price_val * p_mult, 2),
                            currency="INR",
                            observed_at=now - timedelta(days=days_ago),
                            source_status="VERIFIED"
                        )
                        db.add(hist)
            
    # 5. Create Normalized Permissions
    all_permissions = [
        ("READ_PRODUCTS", "Search and view product catalog", "catalog"),
        ("READ_INVENTORY", "Check product stock availability", "inventory"),
        ("CREATE_CART", "Initialize shopping cart", "cart"),
        ("READ_CART", "Inspect current cart contents", "cart"),
        ("MODIFY_CART", "Add or remove items in cart", "cart"),
        ("CALCULATE_CART", "Calculate authoritative cart totals", "cart"),
        ("RECOMMEND_PRODUCT", "Propose discovered products to buyer", "commerce"),
        ("CREATE_RECOMMENDATION", "Generate contextual cross-sells / upsells", "commerce"),
        ("CREATE_PAYMENT_ORDER", "Initialize payment orders", "payment"),
        ("READ_PAYMENT_STATUS", "Check payment confirmation status", "payment"),
        ("RECONCILE_PAYMENT", "Reconcile settled transactions", "payment"),
        ("MANAGE_POLICY", "Configure and update merchant financial policies", "security")
    ]
    
    perm_objs = {}
    for p_name, p_desc, p_cat in all_permissions:
        perm = Permission(name=p_name, description=p_desc, category=p_cat)
        db.add(perm)
        db.flush()
        perm_objs[p_name] = perm

    # 6. Create Normalized Agents & Assign Explicit Permissions (Least Privilege)
    agent_configs = [
        {
            "name": "ShoppingAgent",
            "type": "shopping",
            "version": "1.0.0",
            "model": "gpt-4o-mini",
            "permissions": ["READ_PRODUCTS", "READ_INVENTORY", "CREATE_CART", "READ_CART", "MODIFY_CART", "CALCULATE_CART", "RECOMMEND_PRODUCT"]
        },
        {
            "name": "SalesAgent",
            "type": "sales",
            "version": "1.0.0",
            "model": "gpt-4o-mini",
            "permissions": ["READ_PRODUCTS", "READ_INVENTORY", "READ_CART", "CREATE_RECOMMENDATION"]
        },
        {
            "name": "PaymentAgent",
            "type": "payment",
            "version": "1.0.0",
            "model": "deterministic-guard",
            "permissions": ["CREATE_PAYMENT_ORDER", "READ_PAYMENT_STATUS", "RECONCILE_PAYMENT"]
        }
    ]

    for a_cfg in agent_configs:
        ag = Agent(
            merchant_id=merchant.id,
            name=a_cfg["name"],
            type=a_cfg["type"],
            version=a_cfg["version"],
            model=a_cfg["model"],
            status="active"
        )
        db.add(ag)
        db.flush()
        for p_name in a_cfg["permissions"]:
            if p_name in perm_objs:
                assoc = AgentPermission(agent_id=ag.id, permission_id=perm_objs[p_name].id)
                db.add(assoc)

    # 7. Create Initial Policy (v1)
    policy = Policy(
        merchant_id=merchant.id,
        name="Standard Commerce Control Policy",
        version=1,
        max_transaction_amount=Decimal("10000.00"),
        approval_threshold=Decimal("5000.00"),
        low_risk_limit=Decimal("2000.00"),
        max_discount_percent=Decimal("5.00"),
        max_quantity=5,
        allowed_currency="INR",
        auto_approval_enabled=True,
        authorization_expiration_minutes=10,
        is_active=True,
        created_by_user_id=admin_user.id
    )
    db.add(policy)

    db.commit()
    total_products = db.query(Product).count()
    total_offers = db.query(ExternalProductOffer).count()
    print(f"Database seeded successfully!")
    print(f"- Total Apex Products: {total_products}")
    print(f"- Total External Offers: {total_offers}")
    print(f"- Admin email: {admin_user.email}, Customer email: {customer_user.email}, Password: password123")
    db.close()

if __name__ == "__main__":
    print("Starting database seed with marketplace catalog...")
    seed_db(reset=True)
