import sys
import os
import argparse
import logging
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
from app.database.models.negotiation_policy import MerchantNegotiationPolicy
from app.database.seeds.marketplace_catalog import generate_marketplace_products
from app.services.external_stores.registry import ExternalStoreRegistry
from app.core.security import get_password_hash

logger = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO)


def seed_db(reset: bool = False, db_session: Optional[Session] = None) -> dict:
    """
    Idempotent catalog and database seeder.
    Works seamlessly with both SQLite (local/testing) and PostgreSQL (production Render).
    
    If reset=False (default):
    - Creates missing tables without dropping existing data.
    - Inserts missing merchants, users, stores, products, inventories, and policies.
    - Preserves existing production orders, users, payment transactions, and audit records.
    """
    if db_session is not None:
        db = db_session
        should_close = False
    else:
        if reset:
            logger.warning("Reset requested: Dropping all database tables...")
            Base.metadata.drop_all(bind=engine)

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        should_close = True

    stats = {
        "merchants_created": 0,
        "users_created": 0,
        "stores_created": 0,
        "products_inserted": 0,
        "products_skipped": 0,
        "total_products": 0,
        "external_offers_created": 0,
    }

    try:
        # 1. Create or retrieve Merchant
        merchant = db.query(Merchant).filter(
            (Merchant.name == "Apex Sports Merchant") | (Merchant.domain == "demo-sports.test")
        ).first()

        if not merchant:
            merchant = Merchant(
                id="bdfa40d5-8af9-47b4-942b-8c9a9e3fd78a",
                name="Apex Sports Merchant",
                domain="demo-sports.test",
                is_active=True
            )
            db.add(merchant)
            db.commit()
            db.refresh(merchant)
            stats["merchants_created"] += 1
            logger.info(f"Created primary merchant: {merchant.name} ({merchant.id})")
        else:
            logger.info(f"Using existing merchant: {merchant.name} ({merchant.id})")

        # 2. Create or verify Users (Merchant Admin & Customer)
        admin_user = db.query(User).filter(User.email == "admin@demo-sports.test").first()
        if not admin_user:
            admin_user = User(
                email="admin@demo-sports.test",
                hashed_password=get_password_hash("password123"),
                full_name="Merchant Admin",
                merchant_id=merchant.id,
                role="merchant_admin",
                is_active=True
            )
            db.add(admin_user)
            stats["users_created"] += 1

        # Demo Merchant account for competition / judging
        demo_merchant = db.query(User).filter(User.email == "demo-merchant@apex.test").first()
        if not demo_merchant:
            demo_merchant = User(
                email="demo-merchant@apex.test",
                hashed_password=get_password_hash("ApexDemo@2026"),
                full_name="Apex Demo Merchant",
                merchant_id=merchant.id,
                role="merchant_admin",
                is_active=True
            )
            db.add(demo_merchant)
            stats["users_created"] += 1
        else:
            demo_merchant.role = "merchant_admin"
            demo_merchant.hashed_password = get_password_hash("ApexDemo@2026")
            demo_merchant.merchant_id = merchant.id
            demo_merchant.is_active = True

        customer_user = db.query(User).filter(User.email == "customer@demo-sports.test").first()
        if not customer_user:
            customer_user = User(
                email="customer@demo-sports.test",
                hashed_password=get_password_hash("password123"),
                full_name="Alex Customer",
                merchant_id=merchant.id,
                role="customer",
                is_active=True
            )
            db.add(customer_user)
            stats["users_created"] += 1

        db.commit()
        if admin_user:
            db.refresh(admin_user)
        if demo_merchant:
            db.refresh(demo_merchant)

        # 3. Create or verify External Stores Registry
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
            store = db.query(ExternalStore).filter(ExternalStore.domain == s_info["domain"]).first()
            if not store:
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
                stats["stores_created"] += 1
            store_map[s_info["domain"]] = store

        # 4. Create Marketplace Products & Verified External Offers (Idempotent)
        products_catalog = generate_marketplace_products()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        canonical_names = {p_info["name"].strip().lower() for p_info in products_catalog}
        canonical_skus = {p_info.get("sku").strip().lower() for p_info in products_catalog if p_info.get("sku")}

        # Safe deduplication: keep exactly 1 active record per canonical product, deactivate duplicate copies and leftover test fixtures
        active_existing_prods = db.query(Product).filter(
            Product.merchant_id == merchant.id,
            Product.is_active == True
        ).order_by(Product.created_at.asc(), Product.id.asc()).all()

        duplicates_consolidated = 0
        seen_canonical_names = set()
        seen_canonical_skus = set()

        for ep in active_existing_prods:
            norm_name = (ep.name or "").strip().lower()
            norm_sku = (ep.sku or "").strip().lower() if ep.sku else None
            
            # Check if this active record is in the canonical catalog
            is_canonical = (norm_name in canonical_names) or (norm_sku and norm_sku in canonical_skus)
            
            if is_canonical:
                if norm_name in seen_canonical_names or (norm_sku and norm_sku in seen_canonical_skus):
                    ep.is_active = False
                    duplicates_consolidated += 1
                else:
                    seen_canonical_names.add(norm_name)
                    if norm_sku:
                        seen_canonical_skus.add(norm_sku)
            else:
                # Non-canonical test fixture or legacy artifact: deactivate safely
                ep.is_active = False
                duplicates_consolidated += 1

        if duplicates_consolidated > 0:
            db.flush()
            logger.info(f"Safely consolidated/deactivated {duplicates_consolidated} duplicate or legacy fixture products.")

        # Preload active canonical products for this merchant
        existing_prods = db.query(Product).filter(
            Product.merchant_id == merchant.id,
            Product.is_active == True
        ).all()
        existing_map_by_name = {p.name.strip().lower(): p for p in existing_prods}
        existing_map_by_sku = {p.sku.strip().lower(): p for p in existing_prods if p.sku}

        for p_info in products_catalog:
            p_name = p_info["name"]
            p_sku = p_info.get("sku")
            norm_name = p_name.strip().lower()
            norm_sku = p_sku.strip().lower() if p_sku else None

            existing_p = existing_map_by_name.get(norm_name) or (existing_map_by_sku.get(norm_sku) if norm_sku else None)

            if existing_p:
                # Update attributes, image, and price if changed
                existing_p.image_url = p_info.get("image_url") or existing_p.image_url
                existing_p.attributes = p_info.get("attributes") or existing_p.attributes
                if not existing_p.attributes.get("image_url") and p_info.get("image_url"):
                    existing_p.attributes["image_url"] = p_info.get("image_url")
                existing_p.description = p_info.get("description") or existing_p.description
                existing_p.brand = p_info.get("brand") or existing_p.brand
                stats["products_skipped"] += 1
                p = existing_p
            else:
                # Deterministic product ID mapping for canonical items
                custom_id = None
                if p_name == "Pro Running Shoes":
                    custom_id = "a5bd13a3-9d09-441d-86e0-d08d0bd29f83"
                elif p_name == "Sports Dry-Fit T-Shirt":
                    custom_id = "1866ffbf-0f2a-423a-8e98-d5d921a6b117"

                p_kwargs = {
                    "merchant_id": merchant.id,
                    "name": p_name,
                    "description": p_info["description"],
                    "brand": p_info.get("brand"),
                    "category": p_info["category"],
                    "subcategory": p_info.get("subcategory"),
                    "price": p_info["price"],
                    "mrp": p_info.get("mrp"),
                    "currency": p_info.get("currency", "INR"),
                    "gtin": p_info.get("gtin"),
                    "model_number": p_info.get("model_number"),
                    "sku": p_sku,
                    "image_url": p_info.get("image_url"),
                    "image_urls": [p_info.get("image_url")] if p_info.get("image_url") else [],
                    "rating": p_info.get("rating", 4.5),
                    "review_count": p_info.get("review_count", 0),
                    "tags": p_info.get("tags", []),
                    "variant_group_id": p_info.get("variant_group_id"),
                    "attributes": p_info.get("attributes") or {"image_url": p_info.get("image_url")},
                    "is_active": True,
                    "external_comparison_enabled": True
                }
                if custom_id:
                    p_kwargs["id"] = custom_id

                p = Product(**p_kwargs)
                db.add(p)
                db.flush()
                stats["products_inserted"] += 1
                existing_map_by_name[norm_name] = p
                if norm_sku:
                    existing_map_by_sku[norm_sku] = p

            # Add inventory
            inv = db.query(Inventory).filter(Inventory.product_id == p.id, Inventory.merchant_id == merchant.id).first()
            if not inv:
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
                    stats["external_offers_created"] += 1

                    # Historical price observations
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

        # 5. Create Permissions
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
            perm = db.query(Permission).filter(Permission.name == p_name).first()
            if not perm:
                perm = Permission(name=p_name, description=p_desc, category=p_cat)
                db.add(perm)
                db.flush()
            perm_objs[p_name] = perm

        # 6. Create Agents & Assign Explicit Permissions
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
            ag = db.query(Agent).filter(Agent.merchant_id == merchant.id, Agent.name == a_cfg["name"]).first()
            if not ag:
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

        # 7. Create Policies
        policy = db.query(Policy).filter(Policy.merchant_id == merchant.id, Policy.version == 1).first()
        if not policy:
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
                created_by_user_id=admin_user.id if admin_user else None
            )
            db.add(policy)

        # 8. Create Canonical Negotiation Policy in both tables
        canonical_neg_policy_id = "da3fac75-b80d-4e38-b3eb-9a94dd64d242"

        # A. In `policies` table (ensures PolicyEvaluation foreign key constraint is satisfied)
        gov_neg_policy = db.query(Policy).filter(
            (Policy.id == canonical_neg_policy_id) |
            ((Policy.merchant_id == merchant.id) & (Policy.name == "Standard Negotiation Policy"))
        ).first()
        if not gov_neg_policy:
            gov_neg_policy = Policy(
                id=canonical_neg_policy_id,
                merchant_id=merchant.id,
                name="Standard Negotiation Policy",
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
                created_by_user_id=admin_user.id if admin_user else None
            )
            db.add(gov_neg_policy)
            db.flush()

        # B. In `merchant_negotiation_policies` table
        neg_policy = db.query(MerchantNegotiationPolicy).filter(
            (MerchantNegotiationPolicy.id == canonical_neg_policy_id) |
            ((MerchantNegotiationPolicy.merchant_id == merchant.id) & (MerchantNegotiationPolicy.is_active == True))
        ).first()
        if not neg_policy:
            neg_policy = MerchantNegotiationPolicy(
                id=canonical_neg_policy_id,
                merchant_id=merchant.id,
                tenant_id=merchant.id,
                name="Standard Negotiation Policy",
                enabled=True,
                max_discount_percent=Decimal("5.00"),
                max_discount_amount=Decimal("1000.00"),
                auto_accept_below_discount_percent=Decimal("3.00"),
                approval_above_discount_percent=Decimal("3.00"),
                max_quantity=5,
                min_order_value=Decimal("500.00"),
                allowed_categories=[],
                allowed_products=[],
                currency="INR",
                offer_ttl_minutes=10,
                is_active=True
            )
            db.add(neg_policy)
            db.flush()

        db.commit()
        stats["total_products"] = db.query(Product).filter(Product.is_active == True).count()
        logger.info(f"Database seeding completed successfully: {stats}")
        return stats

    except Exception as e:
        db.rollback()
        logger.exception(f"Error during database seed: {e}")
        raise
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apex Idempotent Database & Catalog Seeder")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables before seeding")
    args = parser.parse_args()

    print("==========================================")
    print("APEX AGENTIC COMMERCE OS — CATALOG SEEDER")
    print("==========================================")
    res = seed_db(reset=args.reset)
    print(f"Products Inserted: {res['products_inserted']}")
    print(f"Products Skipped:  {res['products_skipped']}")
    print(f"Total Active SKUs: {res['total_products']}")
    print("==========================================")
