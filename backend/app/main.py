from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.auth.router import router as auth_router
from app.api.products import router as products_router
from app.api.ai import router as ai_router
from app.api.cart import router as cart_router
from app.api.purchase_intents import router as purchase_intents_router
from app.api.policies import router as policies_router
from app.api.approvals import router as approvals_router
from app.api.agents import router as agents_router
from app.api.payments import router as payments_router
from app.api.orders import router as orders_router
from app.api.rewards import router as rewards_router
from app.api.webhooks import router as webhooks_router
from app.api.audit import router as audit_router
from app.api.health import router as health_router
from app.api.agent_commerce import router as agent_commerce_router
from app.api.ai_commerce import router as ai_commerce_router
from app.protocol.router import router as protocol_router
from app.revenue.router import router as revenue_router
from app.security_lab.router import router as security_lab_router
from app.api.discovery import router as discovery_router
from app.api.personalization import router as personalization_router
from app.api.customer_support import router as support_router
from app.api.price_comparison import router as price_comparison_router
from app.api.price_intelligence import router as price_intelligence_router
from app.api.virtual_tryon import router as virtual_tryon_router
from app.api.agent import router as agent_router
from app.api.negotiation import router as negotiation_router
from app.database.session import engine
from app.database.models.base import Base

# Create tables for initial setup
Base.metadata.create_all(bind=engine)

# Lightweight schema migration for SQLite local databases
try:
    with engine.begin() as conn:
        table_info = conn.exec_driver_sql("PRAGMA table_info(purchase_intents)").fetchall()
        column_names = [row[1] for row in table_info]
        if column_names and "delivery_address" not in column_names:
            conn.exec_driver_sql("ALTER TABLE purchase_intents ADD COLUMN delivery_address JSON DEFAULT '{}'")

        s_table_info = conn.exec_driver_sql("PRAGMA table_info(shopping_sessions)").fetchall()
        s_column_names = [row[1] for row in s_table_info]
        if s_column_names and "context_data" not in s_column_names:
            conn.exec_driver_sql("ALTER TABLE shopping_sessions ADD COLUMN context_data JSON DEFAULT '{}'")

        p_table_info = conn.exec_driver_sql("PRAGMA table_info(products)").fetchall()
        p_column_names = [row[1] for row in p_table_info]
        if p_column_names:
            for col, col_type, col_default in [
                ("brand", "VARCHAR", "NULL"),
                ("subcategory", "VARCHAR", "NULL"),
                ("mrp", "NUMERIC(12, 2)", "NULL"),
                ("gtin", "VARCHAR", "NULL"),
                ("model_number", "VARCHAR", "NULL"),
                ("sku", "VARCHAR", "NULL"),
                ("image_url", "VARCHAR", "NULL"),
                ("image_urls", "JSON", "'[]'"),
                ("rating", "NUMERIC(3, 2)", "4.5"),
                ("review_count", "INTEGER", "0"),
                ("tags", "JSON", "'[]'"),
                ("variant_group_id", "VARCHAR", "NULL"),
                ("external_comparison_enabled", "BOOLEAN", "1")
            ]:
                if col not in p_column_names:
                    conn.exec_driver_sql(f"ALTER TABLE products ADD COLUMN {col} {col_type} DEFAULT {col_default}")

        vto_table_info = conn.exec_driver_sql("PRAGMA table_info(virtual_tryon_jobs)").fetchall()
        vto_column_names = [row[1] for row in vto_table_info]
        if vto_column_names:
            for col, col_type, col_default in [
                ("progress_percent", "INTEGER", "0"),
                ("processing_stage", "VARCHAR", "'PREPARING'"),
                ("progress_message", "VARCHAR", "'Preparing your photo...'"),
                ("sampling_step", "INTEGER", "NULL"),
                ("sampling_total", "INTEGER", "NULL")
            ]:
                if col not in vto_column_names:
                    conn.exec_driver_sql(f"ALTER TABLE virtual_tryon_jobs ADD COLUMN {col} {col_type} DEFAULT {col_default}")

        rev_table_info = conn.exec_driver_sql("PRAGMA table_info(revenue_opportunities)").fetchall()
        rev_column_names = [row[1] for row in rev_table_info]
        # If existing revenue_opportunities table has NOT NULL on confidence, drop and recreate it
        confidence_row = next((row for row in rev_table_info if row[1] == "confidence"), None)
        if confidence_row and confidence_row[3] == 1: # notnull == 1
            conn.exec_driver_sql("DROP TABLE IF EXISTS revenue_opportunities")
            Base.metadata.create_all(bind=engine)
            rev_column_names = []

        if rev_column_names:
            for col, col_type, col_default in [
                ("evidence_json", "JSON", "'{}'"),
                ("calculation_method", "VARCHAR", "NULL"),
                ("data_window", "VARCHAR", "'last_30_days'"),
                ("expires_at", "DATETIME", "NULL"),
                ("idempotency_key", "VARCHAR", "NULL")
            ]:
                if col not in rev_column_names:
                    conn.exec_driver_sql(f"ALTER TABLE revenue_opportunities ADD COLUMN {col} {col_type} DEFAULT {col_default}")

        # Data integrity cleanup: Ensure unverified GTINs for Sports Dry-Fit T-Shirt (style 718833-010) are NULL in database
        conn.exec_driver_sql("UPDATE products SET gtin = NULL WHERE (model_number = '718833-010' OR name = 'Sports Dry-Fit T-Shirt') AND gtin IS NOT NULL")
except Exception:
    pass

# Ensure database has initial catalog on startup (critical for fresh Render PostgreSQL deployments)
try:
    from app.database.session import SessionLocal
    from app.database.models.product import Product
    from scripts.seed import seed_db

    _init_db = SessionLocal()
    if _init_db.query(Product).count() == 0:
        seed_db(reset=False)
    _init_db.close()
except Exception:
    pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    )

app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(products_router, prefix=f"{settings.API_V1_STR}/products", tags=["products"])
app.include_router(price_comparison_router, prefix=f"{settings.API_V1_STR}", tags=["Price Comparison & Market Intelligence"])
app.include_router(price_intelligence_router, prefix=f"{settings.API_V1_STR}", tags=["Buyhatke-style Price Intelligence"])
app.include_router(virtual_tryon_router, prefix=f"{settings.API_V1_STR}", tags=["Virtual Try-On"])
app.include_router(ai_router, prefix=f"{settings.API_V1_STR}/ai", tags=["ai"])
app.include_router(cart_router, prefix=f"{settings.API_V1_STR}/cart", tags=["cart"])
app.include_router(purchase_intents_router, prefix=f"{settings.API_V1_STR}/purchase-intents", tags=["purchase_intents"])
app.include_router(policies_router, prefix=f"{settings.API_V1_STR}/policies", tags=["policies"])
app.include_router(approvals_router, prefix=f"{settings.API_V1_STR}/approvals", tags=["approvals"])
app.include_router(agents_router, prefix=f"{settings.API_V1_STR}/agents", tags=["agents"])
app.include_router(payments_router, prefix=f"{settings.API_V1_STR}/payments", tags=["payments"])
app.include_router(orders_router, prefix=f"{settings.API_V1_STR}/orders", tags=["orders"])
app.include_router(rewards_router, prefix=f"{settings.API_V1_STR}/rewards", tags=["rewards"])
app.include_router(webhooks_router, prefix=f"{settings.API_V1_STR}/webhooks", tags=["webhooks"])
app.include_router(audit_router, prefix=f"{settings.API_V1_STR}/audit", tags=["audit"])
app.include_router(health_router, prefix=f"{settings.API_V1_STR}", tags=["health"])
app.include_router(agent_commerce_router, prefix=f"{settings.API_V1_STR}", tags=["AI-to-AI Commerce"])
app.include_router(ai_commerce_router, prefix=f"{settings.API_V1_STR}", tags=["AI-to-AI Commerce Engine"])
app.include_router(protocol_router, prefix=f"{settings.API_V1_STR}", tags=["AI-to-AI Commerce Protocol"])
app.include_router(revenue_router, prefix=f"{settings.API_V1_STR}", tags=["Revenue Autopilot"])
app.include_router(security_lab_router, prefix=f"{settings.API_V1_STR}", tags=["AI Red-Team Security Lab"])
app.include_router(discovery_router, prefix=f"{settings.API_V1_STR}/search", tags=["Multimodal Discovery"])
app.include_router(personalization_router, prefix=f"{settings.API_V1_STR}/personalization", tags=["Personalization Engine"])
app.include_router(support_router, prefix=f"{settings.API_V1_STR}/customer/support", tags=["AI Customer Support"])
app.include_router(agent_router, prefix=f"{settings.API_V1_STR}", tags=["Agent Commerce & Buyer Agent"])
app.include_router(negotiation_router, prefix=f"{settings.API_V1_STR}", tags=["Agentic Price Negotiation"])

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Agentic Commerce OS"}
