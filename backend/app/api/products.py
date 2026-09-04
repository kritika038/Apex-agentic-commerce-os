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
        attributes=p.attributes or {},
        is_active=p.is_active,
        stock_quantity=stock,
        in_stock=stock > 0,
        image_url=img,
        lowest_market_price=lowest_market,
        external_stores_count=ext_count,
        external_comparison_enabled=p.external_comparison_enabled
    )

@router.get("", response_model=List[ProductResponse])
@router.get("/", response_model=List[ProductResponse])
def read_products(
    skip: int = 0, 
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
        q = q.order_by(Product.created_at.asc())

    products = q.offset(skip).limit(limit).all()

    enriched = [_enrich_product(p) for p in products]
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
