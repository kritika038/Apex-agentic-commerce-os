from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.database.session import get_db
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.services.discovery_service import MultimodalDiscoveryService

router = APIRouter()

class SearchConversationalRequest(BaseModel):
    query: str
    merchant_id: Optional[str] = None

class SearchVisualResponse(BaseModel):
    results: List[Dict[str, Any]]
    total_found: int
    algorithm: str = "Color-Spatial Normalized Cosine Similarity"

@router.post("/conversational")
def search_conversational(
    payload: SearchConversationalRequest,
    db: Session = Depends(get_db)
):
    """
    Parses conversational search intent across English, Hindi, Hinglish, and ASR.
    Returns structured intent and candidate catalog products.
    """
    intent = MultimodalDiscoveryService.parse_search_intent(payload.query)

    merchant_id = payload.merchant_id
    q = db.query(Product).filter(Product.is_active == True)
    if merchant_id:
        # Check if merchant exists
        m_count = db.query(Product).filter(Product.merchant_id == merchant_id, Product.is_active == True).count()
        if m_count > 0:
            q = q.filter(Product.merchant_id == merchant_id)
    cat = intent.get("category")
    if cat:
        if cat in ["Footwear", "Running"]:
            q = q.filter(Product.category.in_(["Footwear", "Running"]))
        else:
            q = q.filter(Product.category == cat)
    if intent.get("budget_max"):
        q = q.filter(Product.price <= intent["budget_max"])

    products = q.limit(6).all()
    
    return {
        "intent": intent,
        "total_results": len(products),
        "products": [
            {
                "id": str(p.id),
                "name": p.name,
                "category": p.category,
                "price": float(p.price),
                "stock_quantity": p.inventory.stock_quantity if p.inventory else 10,
                "in_stock": (p.inventory.stock_quantity if p.inventory else 10) > 0,
                "image_url": (p.attributes or {}).get("image_url"),
                "description": p.description
            }
            for p in products
        ]
    }

@router.post("/visual", response_model=SearchVisualResponse)
async def search_visual(
    file: UploadFile = File(...),
    merchant_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Multimodal Visual Search endpoint.
    Performs cosine similarity ranking between query image features and catalog product image profiles.
    """
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image uploaded.")

    m = db.query(Merchant).first()
    target_merchant_id = merchant_id or (m.id if m else "")

    results = MultimodalDiscoveryService.visual_search(
        db=db,
        merchant_id=target_merchant_id,
        image_bytes=contents,
        top_k=4
    )

    return SearchVisualResponse(
        results=results,
        total_found=len(results),
        algorithm="Color-Spatial Normalized Cosine Similarity"
    )

@router.get("/filters")
def get_catalog_filters(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Returns live dynamic filters derived from authoritative catalog data.
    """
    m = db.query(Merchant).first()
    target_merchant_id = merchant_id or (m.id if m else "")

    products = db.query(Product).filter(
        Product.merchant_id == target_merchant_id,
        Product.is_active == True
    ).all()

    categories = sorted(list({p.category for p in products}))
    prices = [float(p.price) for p in products]
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 10000

    return {
        "categories": categories,
        "price_bounds": {
            "min": min_price,
            "max": max_price
        },
        "use_cases": ["Running", "Gym & Workout", "Marathon Training", "Recovery", "Daily Athletic"],
        "styles": ["Performance", "Premium", "Casual Endurance"]
    }
