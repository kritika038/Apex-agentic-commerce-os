"""
Authoritative Agent-Readable Catalog Service.
Transforms SQLite/PostgreSQL relational catalog and canonical graph into structured,
machine-readable, transaction-ready contracts for external and internal AI buyer agents.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.database.models.base import generate_uuid
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.merchant import Merchant
from app.schemas.agent_catalog import (
    AgentVariantItem,
    AgentProductDetail,
    AgentCatalogResponse,
    AgentSearchRequest,
    AgentSearchResponse,
    AgentAvailabilityResponse,
)

class AgentCatalogService:
    @classmethod
    def enrich_product_detail(cls, product: Product) -> AgentProductDetail:
        """
        Derives machine-readable product structure, variants, canonical identity,
        purchase constraints, and server-determined agent buyability.
        """
        stock = product.inventory.stock_quantity if product.inventory else 0
        attrs = product.attributes if isinstance(product.attributes, dict) else {}
        
        # 1. Determine Agent Buyability
        agent_buyable = True
        reason = None

        if not product.is_active:
            agent_buyable = False
            reason = "INACTIVE_PRODUCT"
        elif product.merchant and not product.merchant.is_active:
            agent_buyable = False
            reason = "MERCHANT_DISABLED"
        elif product.price is None or float(product.price) <= 0:
            agent_buyable = False
            reason = "INVALID_PRICE"
        elif stock <= 0:
            agent_buyable = False
            reason = "OUT_OF_STOCK"
        elif (product.currency or "INR").upper() != "INR":
            agent_buyable = False
            reason = "COMMERCE_UNAVAILABLE"

        # 2. Extract First-Class Structured Variants
        variant_details = attrs.get("variant_details") or attrs.get("variants") or {}
        variant_images = attrs.get("variant_images") or {}
        vto_ready = bool(attrs.get("vto_image_ready", False))
        
        variants_list: List[AgentVariantItem] = []

        if variant_details and isinstance(variant_details, dict):
            for v_key, v_val in variant_details.items():
                if isinstance(v_val, dict):
                    v_color = v_val.get("color", v_key)
                    v_size = v_val.get("size", attrs.get("size", "Standard"))
                    v_style = v_val.get("style_code") or attrs.get("style_code") or product.model_number
                    v_gtin = v_val.get("gtin") or attrs.get("gtin") or product.gtin
                    v_asset = v_val.get("garment_image_url") or v_val.get("vto_image_url") or variant_images.get(v_key)
                    v_price = float(v_val.get("price", product.price))
                    v_mrp = float(v_val.get("mrp", product.mrp)) if product.mrp else None
                    v_stock = int(v_val.get("stock_quantity", stock))
                    
                    variants_list.append(AgentVariantItem(
                        variant_id=v_key,
                        display_name=f"{product.name} ({v_color} - {v_size})",
                        color=v_color,
                        size=v_size,
                        style_code=v_style,
                        gtin=v_gtin,
                        price=v_price,
                        mrp=v_mrp,
                        currency=product.currency or "INR",
                        availability="in_stock" if v_stock > 0 else "out_of_stock",
                        inventory_available=v_stock > 0,
                        stock_quantity=v_stock,
                        garment_asset=v_asset,
                        vto_eligible=vto_ready and bool(v_asset)
                    ))
        elif variant_images and isinstance(variant_images, dict):
            for v_key, v_img in variant_images.items():
                variants_list.append(AgentVariantItem(
                    variant_id=v_key,
                    display_name=f"{product.name} ({v_key})",
                    color=v_key,
                    size=attrs.get("size", "Standard"),
                    style_code=attrs.get("style_code") or product.model_number,
                    gtin=attrs.get("gtin") or product.gtin,
                    price=float(product.price),
                    mrp=float(product.mrp) if product.mrp else None,
                    currency=product.currency or "INR",
                    availability="in_stock" if stock > 0 else "out_of_stock",
                    inventory_available=stock > 0,
                    stock_quantity=stock,
                    garment_asset=v_img,
                    vto_eligible=vto_ready and bool(v_img)
                ))
        else:
            # Single primary variant
            primary_color = attrs.get("color") or "Standard"
            primary_size = attrs.get("size") or "Standard"
            primary_asset = attrs.get("vto_image_url") or product.image_url
            variants_list.append(AgentVariantItem(
                variant_id=f"{primary_color}-{primary_size}",
                display_name=f"{product.name} ({primary_color} - {primary_size})",
                color=primary_color,
                size=primary_size,
                style_code=attrs.get("style_code") or product.model_number,
                gtin=attrs.get("gtin") or product.gtin,
                price=float(product.price),
                mrp=float(product.mrp) if product.mrp else None,
                currency=product.currency or "INR",
                availability="in_stock" if stock > 0 else "out_of_stock",
                inventory_available=stock > 0,
                stock_quantity=stock,
                garment_asset=primary_asset,
                vto_eligible=vto_ready and bool(primary_asset)
            ))

        # 3. Canonical Identity
        canonical_id = {
            "brand": product.brand or "Apex",
            "model": product.model_number or attrs.get("model"),
            "style_code": attrs.get("style_code") or product.model_number,
            "gtin": attrs.get("gtin") or product.gtin,
            "verified": bool(attrs.get("canonical_verified", True)),
        }

        # 4. Purchase Constraints
        constraints = {
            "max_order_quantity": 5,
            "requires_approval_above": 5000.0,
            "policy_blocked_above": 10000.0,
            "allowed_currency": "INR",
            "supported_payment_provider": "RAZORPAY_TEST_MODE"
        }

        img = product.image_url or attrs.get("image_url")

        return AgentProductDetail(
            product_id=str(product.id),
            merchant_id=str(product.merchant_id),
            name=product.name,
            description=product.description,
            brand=product.brand or "Apex",
            category=product.category,
            subcategory=product.subcategory,
            currency=product.currency or "INR",
            price=float(product.price),
            mrp=float(product.mrp) if product.mrp else None,
            availability="in_stock" if stock > 0 else "out_of_stock",
            inventory_available=stock > 0,
            stock_quantity=stock,
            variants=variants_list,
            attributes=attrs,
            agent_buyable=agent_buyable,
            agent_buyability_reason=reason,
            purchase_constraints=constraints,
            canonical_identity=canonical_id,
            image_url=img
        )

    @classmethod
    def get_catalog(
        cls,
        db: Session,
        skip: int = 0,
        limit: int = 50,
        query: Optional[str] = None,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        budget_max: Optional[float] = None,
        min_price: Optional[float] = None,
        availability: Optional[str] = None,
        merchant_id: Optional[str] = None
    ) -> AgentCatalogResponse:
        q = db.query(Product).filter(Product.is_active == True)
        
        if merchant_id:
            q = q.filter(Product.merchant_id == merchant_id)
        if category and category.lower() != "all":
            q = q.filter(Product.category.ilike(f"%{category}%"))
        if brand:
            q = q.filter(Product.brand.ilike(f"%{brand}%"))
        if budget_max is not None:
            q = q.filter(Product.price <= Decimal(str(budget_max)))
        if min_price is not None:
            q = q.filter(Product.price >= Decimal(str(min_price)))
        if query:
            q = q.filter(
                (Product.name.ilike(f"%{query}%")) |
                (Product.description.ilike(f"%{query}%")) |
                (Product.brand.ilike(f"%{query}%")) |
                (Product.category.ilike(f"%{query}%"))
            )

        total = q.count()
        products = q.order_by(Product.price.asc()).offset(skip).limit(limit).all()

        details: List[AgentProductDetail] = []
        for p in products:
            item = cls.enrich_product_detail(p)
            if availability == "in_stock" and not item.inventory_available:
                continue
            details.append(item)

        return AgentCatalogResponse(
            total=total,
            skip=skip,
            limit=limit,
            currency="INR",
            generated_at=datetime.now(timezone.utc).isoformat(),
            products=details
        )

    @classmethod
    def get_product_by_id(cls, db: Session, product_id: str) -> AgentProductDetail:
        p = db.query(Product).filter(Product.id == product_id).first()
        if not p:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID '{product_id}' not found.")
        return cls.enrich_product_detail(p)

    @classmethod
    def search_catalog(cls, db: Session, request: AgentSearchRequest) -> AgentSearchResponse:
        """
        Executes structured search with strict HARD CONSTRAINTS FIRST:
        Budget, Brand, Category, Availability filters are strictly applied before ranking.
        """
        q = db.query(Product).filter(Product.is_active == True)
        if request.availability == "in_stock":
            q = q.join(Inventory, Product.id == Inventory.product_id).filter(Inventory.stock_quantity > 0)

        # 1. Hard Filter: Merchant
        if request.merchant_id:
            q = q.filter(Product.merchant_id == request.merchant_id)

        # 2. Hard Filter: Category
        if request.category and request.category.lower() != "all":
            cat_clean = request.category.lower().strip()
            if cat_clean in ["running", "shoes", "running shoes", "footwear"]:
                q = q.filter(
                    (Product.category.ilike("%running%")) |
                    (Product.category.ilike("%footwear%")) |
                    (Product.category.ilike("%shoes%")) |
                    (Product.name.ilike("%running%")) |
                    (Product.name.ilike("%shoe%"))
                )
            elif cat_clean in ["bottle", "bottles", "water bottle", "water bottles"]:
                q = q.filter(
                    (Product.category.ilike("%bottle%")) |
                    (Product.name.ilike("%bottle%"))
                )
            else:
                q = q.filter(
                    (Product.category.ilike(f"%{cat_clean}%")) |
                    (Product.subcategory.ilike(f"%{cat_clean}%"))
                )

        # 3. Hard Filter: Brand (Single or List)
        if request.brand:
            if isinstance(request.brand, list):
                brands_list = [b.lower().strip() for b in request.brand if b]
                if brands_list:
                    from sqlalchemy import or_
                    q = q.filter(or_(*[Product.brand.ilike(f"%{b}%") for b in brands_list]))
            elif isinstance(request.brand, str) and request.brand.strip():
                b_str = request.brand.strip()
                q = q.filter(Product.brand.ilike(f"%{b_str}%"))

        # 4. Hard Filter: Budget Max & Min
        if request.budget_max is not None:
            q = q.filter(Product.price <= Decimal(str(request.budget_max)))
        if request.min_price is not None:
            q = q.filter(Product.price >= Decimal(str(request.min_price)))

        # 5. Natural Query Keyword Matching
        if request.query:
            query_str = request.query.strip()
            q = q.filter(
                (Product.name.ilike(f"%{query_str}%")) |
                (Product.description.ilike(f"%{query_str}%")) |
                (Product.brand.ilike(f"%{query_str}%")) |
                (Product.category.ilike(f"%{query_str}%"))
            )

        # Sorting
        if request.sort == "price_asc":
            q = q.order_by(Product.price.asc())
        elif request.sort == "price_desc":
            q = q.order_by(Product.price.desc())
        elif request.sort == "rating_desc":
            q = q.order_by(Product.rating.desc(), Product.price.asc())
        else:
            q = q.order_by(Product.price.asc())

        total = q.count()
        raw_products = q.offset(request.skip).limit(request.limit).all()

        results: List[AgentProductDetail] = []
        for p in raw_products:
            detail = cls.enrich_product_detail(p)
            
            # Filter by variant color / size if specified
            if request.color:
                c_req = request.color.lower().strip()
                has_color = any(c_req in (v.color or "").lower() for v in detail.variants)
                if not has_color and c_req not in (detail.attributes.get("color") or "").lower():
                    continue
            
            if request.size:
                s_req = request.size.lower().strip()
                has_size = any(s_req == (v.size or "").lower() for v in detail.variants)
                if not has_size and s_req != (detail.attributes.get("size") or "").lower():
                    continue

            if request.availability == "in_stock" and not detail.inventory_available:
                continue

            results.append(detail)

        applied = {
            "query": request.query,
            "budget_max": request.budget_max,
            "min_price": request.min_price,
            "brand": request.brand,
            "category": request.category,
            "color": request.color,
            "size": request.size,
            "availability": request.availability or "all"
        }

        return AgentSearchResponse(
            results=results,
            total=len(results),
            applied_filters=applied,
            search_id=f"srch_{generate_uuid()[:12]}",
            generated_at=datetime.now(timezone.utc).isoformat()
        )

    @classmethod
    def get_product_availability(cls, db: Session, product_id: str) -> AgentAvailabilityResponse:
        p = db.query(Product).filter(Product.id == product_id).first()
        if not p:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID '{product_id}' not found.")
        
        detail = cls.enrich_product_detail(p)
        var_avail = [
            {
                "variant_id": v.variant_id,
                "display_name": v.display_name,
                "color": v.color,
                "size": v.size,
                "in_stock": v.inventory_available,
                "stock_quantity": v.stock_quantity,
                "availability": v.availability
            }
            for v in detail.variants
        ]

        return AgentAvailabilityResponse(
            product_id=str(p.id),
            is_active=p.is_active,
            in_stock=detail.inventory_available,
            stock_quantity=detail.stock_quantity,
            availability=detail.availability,
            agent_buyable=detail.agent_buyable,
            agent_buyability_reason=detail.agent_buyability_reason,
            variants_availability=var_avail,
            checked_at=datetime.now(timezone.utc).isoformat()
        )
