"""
Authoritative Deterministic Virtual Try-On Catalog Coverage Audit.
Analyzes catalog products, validates garment eligibility, inspects variant mappings,
and guarantees exact asset resolution integrity.
"""

from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.database.models.product import Product
from app.services.virtual_tryon.service import VirtualTryOnService

def audit_vto_catalog(db: Session) -> Dict[str, Any]:
    """
    Executes a comprehensive, deterministic audit of all catalog products for VTO readiness.
    """
    products = db.query(Product).filter(Product.is_active == True).all()

    eligible_clothing_products: List[Dict[str, Any]] = []
    non_eligible_products: List[Dict[str, Any]] = []
    variants_with_valid_garment_asset: List[Dict[str, Any]] = []
    variants_missing_garment_asset: List[Dict[str, Any]] = []
    invalid_assets: List[Dict[str, Any]] = []
    wrong_variant_mapping: List[Dict[str, Any]] = []
    wrong_category: List[Dict[str, Any]] = []

    for product in products:
        eligibility = VirtualTryOnService.is_virtual_tryon_supported(product)
        
        if not eligibility.supported:
            non_eligible_products.append({
                "product_id": str(product.id),
                "name": product.name,
                "category": product.category,
                "subcategory": product.subcategory,
                "reason": eligibility.reason
            })
            continue

        # Product is an eligible apparel item
        attrs = product.attributes if isinstance(product.attributes, dict) else {}
        variant_details = attrs.get("variant_details") or attrs.get("variants") or {}
        variant_images = attrs.get("variant_images") or {}

        # Enumerate all known variants for this product
        variant_names = list(variant_details.keys()) or list(variant_images.keys())
        if not variant_names and attrs.get("color"):
            variant_names = [attrs.get("color")]
        if not variant_names:
            variant_names = ["Standard"]

        product_entry = {
            "product_id": str(product.id),
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "subcategory": product.subcategory,
            "garment_type": eligibility.garment_type,
            "variants_count": len(variant_names),
            "variants": variant_names
        }
        eligible_clothing_products.append(product_entry)

        for var_name in variant_names:
            var_record = {
                "product_id": str(product.id),
                "product_name": product.name,
                "variant_id": var_name,
                "garment_type": eligibility.garment_type
            }

            try:
                garment_url, meta = VirtualTryOnService.resolve_variant_garment(product, var_name)
                if not garment_url:
                    variants_missing_garment_asset.append(var_record)
                elif not (garment_url.startswith("http://") or garment_url.startswith("https://") or garment_url.startswith("/")):
                    invalid_assets.append({**var_record, "asset_url": garment_url, "reason": "Invalid URL scheme"})
                else:
                    variants_with_valid_garment_asset.append({
                        **var_record,
                        "garment_asset": garment_url,
                        "color": meta.get("color"),
                        "style_code": meta.get("style_code"),
                        "gtin": meta.get("gtin")
                    })
            except ValueError as ve:
                err_msg = str(ve)
                if "No verified garment asset" in err_msg:
                    variants_missing_garment_asset.append({**var_record, "reason": err_msg})
                elif "category" in err_msg.lower():
                    wrong_category.append({**var_record, "reason": err_msg})
                else:
                    wrong_variant_mapping.append({**var_record, "reason": err_msg})
            except Exception as ex:
                wrong_variant_mapping.append({**var_record, "reason": str(ex)})

    total_variants = len(variants_with_valid_garment_asset) + len(variants_missing_garment_asset) + len(wrong_variant_mapping)
    coverage_pct = round((len(variants_with_valid_garment_asset) / max(1, total_variants)) * 100, 2)

    return {
        "total_catalog_products": len(products),
        "total_eligible_clothing_products": len(eligible_clothing_products),
        "total_non_eligible_products": len(non_eligible_products),
        "eligible_clothing_products": eligible_clothing_products,
        "non_eligible_products": non_eligible_products,
        "total_eligible_variants": total_variants,
        "variants_with_valid_garment_asset_count": len(variants_with_valid_garment_asset),
        "variants_with_valid_garment_asset": variants_with_valid_garment_asset,
        "variants_missing_garment_asset_count": len(variants_missing_garment_asset),
        "variants_missing_garment_asset": variants_missing_garment_asset,
        "invalid_assets_count": len(invalid_assets),
        "invalid_assets": invalid_assets,
        "wrong_variant_mapping_count": len(wrong_variant_mapping),
        "wrong_variant_mapping": wrong_variant_mapping,
        "wrong_category_count": len(wrong_category),
        "wrong_category": wrong_category,
        "coverage_percentage": coverage_pct,
        "is_catalog_vto_ready": len(variants_missing_garment_asset) == 0 and len(wrong_variant_mapping) == 0
    }
