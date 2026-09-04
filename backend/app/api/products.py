from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.database.models.product import Product
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.schemas.product import ProductResponse, ProductCreate, ProductUpdate
from app.auth.deps import get_current_active_user, get_optional_current_user

router = APIRouter()

def _enrich_product(p: Product) -> ProductResponse:
    stock = p.inventory.stock_quantity if p.inventory else 0
    img = p.image_url or ((p.attributes or {}).get("image_url") if isinstance(p.attributes, dict) else None)
    
    # Calculate lowest market price if external offers exist
    lowest_market = None
    ext_count = 0
    if p.external_offers:
        ext_count = len(p.external_offers)
        prices = [float(off.price) for off in p.external_offers if off.price]
        if prices:
            lowest_market = min(prices)

    attrs = p.attributes if isinstance(p.attributes, dict) else {}
    variants = attrs.get("variants", [])
    available_colors = attrs.get("available_colors", [])
    available_sizes = attrs.get("available_sizes", [])
    
    # Derive colors/sizes from variant_details or variant_images if not explicitly in attributes
    cat_sub_name = f"{(p.category or '').lower()} {(p.subcategory or '').lower()} {(p.name or '').lower()}"

    if not available_colors:
        if "variant_details" in attrs and isinstance(attrs["variant_details"], dict):
            available_colors = list(attrs["variant_details"].keys())
        elif "variant_images" in attrs and isinstance(attrs["variant_images"], dict):
            available_colors = list(attrs["variant_images"].keys())
        elif "color" in attrs and attrs["color"]:
            available_colors = [str(attrs["color"])]
        elif any(k in cat_sub_name for k in ["shoe", "sneaker", "cleat", "spike", "shirt", "pant", "short", "jacket", "bra", "apparel", "running", "fitness"]):
            available_colors = ["Standard Edition"]

    if not available_sizes:
        if "available_sizes" in attrs and isinstance(attrs["available_sizes"], list):
            available_sizes = attrs["available_sizes"]
        elif "size" in attrs and attrs["size"]:
            available_sizes = [str(attrs["size"])]
        elif any(k in cat_sub_name for k in ["shoe", "shoes", "sneaker", "sneakers", "spikes", "cleats", "pegasus", "ultraboost"]):
            available_sizes = ["UK 7", "UK 8", "UK 9", "UK 10", "UK 11"]
        elif any(k in cat_sub_name for k in ["t-shirt", "shirt", "pant", "short", "jacket", "bra", "track", "apparel", "wear", "tee"]):
            available_sizes = ["S", "M", "L", "XL"]

    # Compute min and max price across variants
    min_p = p.price
    max_p = p.price
    if variants and isinstance(variants, list):
        v_prices = [Decimal(str(v["price"])) for v in variants if "price" in v and v["price"] is not None]
        if v_prices:
            min_p = min(v_prices)
            max_p = max(v_prices)

    variants_cnt = max(1, len(variants)) if variants else (len(available_colors) if len(available_colors) > 1 else 1)

    return ProductResponse(
        id=str(p.id),
        merchant_id=str(p.merchant_id),
        name=p.name,
        description=p.description,
        brand=p.brand,
        category=p.category,
        subcategory=p.subcategory,
        price=p.price,
        mrp=p.mrp,
        currency=p.currency or "INR",
        gtin=p.gtin,
        model_number=p.model_number,
        sku=p.sku,
        rating=float(p.rating) if p.rating else 4.5,
        review_count=p.review_count or 0,
        tags=p.tags or [],
        attributes=attrs,
        is_active=p.is_active,
        stock_quantity=stock,
        in_stock=stock > 0,
        image_url=img,
        lowest_market_price=lowest_market,
        external_stores_count=ext_count,
        external_comparison_enabled=p.external_comparison_enabled,
        variants_count=variants_cnt,
        available_colors=available_colors,
        available_sizes=available_sizes,
        min_price=min_p,
        max_price=max_p,
        variants=variants
    )

@router.get("", response_model=List[ProductResponse])
@router.get("/", response_model=List[ProductResponse])
def read_products(
    skip: int = 0, 
    offset: Optional[int] = None,
    limit: int = 300, 
    query: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    brand: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    rating_min: Optional[float] = None,
    sort_by: Optional[str] = None, # price_asc, price_desc, rating_desc, newest
    in_stock_only: Optional[bool] = False,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    target_merchant_id = None

    if merchant_id:
        target_merchant_id = merchant_id
    elif current_user and current_user.merchant_id:
        target_merchant_id = current_user.merchant_id
    else:
        m = db.query(Merchant).first()
        if m:
            target_merchant_id = m.id

    if not target_merchant_id:
        return []

    q = db.query(Product).filter(
        Product.merchant_id == target_merchant_id,
        Product.is_active == True
    )

    if category and category.lower() != "all":
        if category.lower() in ["running", "footwear", "shoes"]:
            q = q.filter(
                (Product.category.ilike("%running%")) | 
                (Product.category.ilike("%footwear%")) |
                (Product.category.ilike("%sports%"))
            )
        else:
            q = q.filter(Product.category.ilike(f"%{category}%"))

    if subcategory:
        q = q.filter(Product.subcategory.ilike(f"%{subcategory}%"))

    if brand and brand.lower() != "all":
        q = q.filter(Product.brand.ilike(f"%{brand}%"))

    if max_price is not None:
        q = q.filter(Product.price <= Decimal(str(max_price)))
    if min_price is not None:
        q = q.filter(Product.price >= Decimal(str(min_price)))
    if rating_min is not None:
        q = q.filter(Product.rating >= Decimal(str(rating_min)))

    if query:
        search_terms = query.strip().split()
        for term in search_terms:
            q = q.filter(
                (Product.name.ilike(f"%{term}%")) | 
                (Product.category.ilike(f"%{term}%")) | 
                (Product.subcategory.ilike(f"%{term}%")) | 
                (Product.brand.ilike(f"%{term}%")) | 
                (Product.description.ilike(f"%{term}%"))
            )

    # Sorting
    if sort_by == "price_asc":
        q = q.order_by(Product.price.asc())
    elif sort_by == "price_desc":
        q = q.order_by(Product.price.desc())
    elif sort_by == "rating_desc":
        q = q.order_by(Product.rating.desc())
    elif sort_by == "newest":
        q = q.order_by(Product.created_at.desc())
    else:
        q = q.order_by(Product.created_at.asc(), Product.id.asc())

    raw_products = q.all()

    # Storefront Canonical Product Family Deduplication:
    # Exactly one card per physical canonical product family
    seen_families = set()
    deduped_products: List[Product] = []

    for p in raw_products:
        norm_name = p.name.lower().strip()
        norm_brand = (p.brand or "").lower().strip()
        
        # Strip synthetic/legacy variant suffixes like " (Crimson Red - XL)" if present
        base_name = norm_name
        if " (" in base_name and base_name.endswith(")"):
            base_name = base_name.split(" (")[0].strip()

        family_key = (
            p.variant_group_id
            or (f"{norm_brand}::{base_name}" if norm_brand else base_name)
        )
        if family_key not in seen_families:
            seen_families.add(family_key)
            deduped_products.append(p)

    actual_skip = offset if offset is not None else skip
    paginated = deduped_products[actual_skip : actual_skip + limit]
    enriched = [_enrich_product(p) for p in paginated]
    if in_stock_only:
        enriched = [p for p in enriched if p.in_stock]
    return enriched

@router.get("/{product_id}", response_model=ProductResponse)
def read_product(
    product_id: str, 
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    q = db.query(Product).filter(Product.id == product_id)
    if merchant_id:
        q = q.filter(Product.merchant_id == merchant_id)
    elif current_user and current_user.merchant_id:
        q = q.filter(Product.merchant_id == current_user.merchant_id)
    else:
        q = q.filter(Product.is_active == True)
    product = q.first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _enrich_product(product)

@router.post("/", response_model=ProductResponse)
@router.post("", response_model=ProductResponse)
def create_product(
    product_in: ProductCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role == "customer" or not current_user.merchant_id:
        raise HTTPException(status_code=403, detail="Merchant Admin privileges required to create products.")
    
    product_data = product_in.model_dump()
    stock = product_data.pop("stock_quantity", 0)
    
    product = Product(
        **product_data,
        merchant_id=current_user.merchant_id
    )
    db.add(product)
    db.flush()
    
    from app.database.models.inventory import Inventory
    inventory = Inventory(
        merchant_id=current_user.merchant_id,
        product_id=product.id,
        stock_quantity=stock
    )
    db.add(inventory)
    db.commit()
    db.refresh(product)
    return _enrich_product(product)

@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str, 
    product_in: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role == "customer" or not current_user.merchant_id:
        raise HTTPException(status_code=403, detail="Merchant Admin privileges required to update products.")

    product = db.query(Product).filter(
        Product.id == product_id, 
        Product.merchant_id == current_user.merchant_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = product_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
        
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

@router.delete("/{product_id}")
def delete_product(
    product_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role == "customer" or not current_user.merchant_id:
        raise HTTPException(status_code=403, detail="Merchant Admin privileges required to delete products.")

    product = db.query(Product).filter(
        Product.id == product_id, 
        Product.merchant_id == current_user.merchant_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db.delete(product)
    db.commit()
    return {"ok": True}
