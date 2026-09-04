import os
import io
import uuid
import logging
import mimetypes
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List
from decimal import Decimal
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database.models.product import Product
from app.database.models.virtual_tryon import VirtualTryOnJob, VirtualTryOnEvent, TryOnGarmentType, TryOnJobStatus
from app.services.virtual_tryon.registry import VTOProviderRegistry
from app.schemas.virtual_tryon import (
    TryOnEligibilityResponse,
    StyleRecommendationItem,
    MerchantVTOReadinessItem,
    MerchantVTOStatsResponse
)

# Supported extensions and magic byte signatures
ALLOWED_MIME_TYPES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"]
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "vto_media")
os.makedirs(STORAGE_DIR, exist_ok=True)

class VirtualTryOnService:

    # -------------------------------------------------------------
    # 1. Deterministic Eligibility & Garment Classification
    # -------------------------------------------------------------

    CLOTHING_KEYWORDS = [
        "t-shirt", "tshirt", "shirt", "top", "dress", "jacket", "coat", "hoodie", 
        "sweater", "sweatshirt", "jeans", "trouser", "pants", "shorts", "skirt", 
        "apparel", "jersey", "tracksuit", "kurta", "tee", "windbreaker", "tank top", "leggings"
    ]

    FOOTWEAR_KEYWORDS = [
        "shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers", 
        "football", "basketball shoe", "sandal", "sandals", "slide", "slides", "boot", 
        "boots", "footwear", "cleats", "pegasus", "speedflow", "running shoe", "running shoes"
    ]

    UNSUPPORTED_KEYWORDS = [
        "bottle", "shaker", "water bottle", "watch", "smartwatch", "tracker", "gps", "fitness tracker",
        "earbud", "earbuds", "headphone", "headphones", "speaker", "speakers", "gadget", "electronics", 
        "dumbbell", "kettlebell", "mat", "yoga mat", "band", "resistance band", "furniture", "bag", "backpack",
        "duffle", "luggage", "trolley", "cookware", "pan", "pot", "mixer", "grinder", "blender", "juicer",
        "casserole", "mug", "shaver", "trimmer", "dryer", "skincare", "moisturizer", "cream", "supplement", "protein",
        "roller", "foam roller", "jump rope", "skipping rope", "gloves", "mouse", "keyboard", "monitor", "power bank"
    ]

    @classmethod
    def is_virtual_tryon_supported(cls, product: Product) -> TryOnEligibilityResponse:
        name_lower = (product.name or "").lower()
        cat_lower = (product.category or "").lower()
        subcat_lower = (product.subcategory or "").lower()
        combined = f"{name_lower} {cat_lower} {subcat_lower}"

        # 1. Reject explicitly unsupported categories
        for unsupp in cls.UNSUPPORTED_KEYWORDS:
            if unsupp in name_lower or unsupp in cat_lower or unsupp in subcat_lower:
                return TryOnEligibilityResponse(
                    supported=False,
                    product_id=str(product.id),
                    product_name=product.name,
                    category=product.category,
                    subcategory=product.subcategory,
                    reason=f"Product category '{product.category}' does not support virtual try-on.",
                    recommended_photo_type="none",
                    product_image_url=product.image_url
                )

        # 2. Check for usable image asset
        if not product.image_url or not product.image_url.strip():
            return TryOnEligibilityResponse(
                supported=False,
                product_id=str(product.id),
                product_name=product.name,
                category=product.category,
                subcategory=product.subcategory,
                reason="Product does not have usable high-resolution imagery for virtual try-on.",
                recommended_photo_type="none",
                product_image_url=None
            )

        # 3. Footwear currently unsupported for VTO
        is_footwear = (
            any(k in combined for k in cls.FOOTWEAR_KEYWORDS) or 
            cat_lower in ["footwear", "running"] or
            subcat_lower in ["running shoes", "sneakers", "training shoes", "football shoes", "basketball shoes", "casual shoes", "sandals", "shoes"]
        )
        if is_footwear:
            return TryOnEligibilityResponse(
                supported=False,
                product_id=str(product.id),
                product_name=product.name,
                garment_type="FOOTWEAR",
                category=product.category,
                subcategory=product.subcategory or "Footwear",
                reason="Virtual try-on currently supports apparel only.",
                recommended_photo_type="none",
                product_image_url=product.image_url
            )

        # 4. Check VTO Image Readiness
        vto_image_ready = True
        if product.attributes and isinstance(product.attributes, dict):
            if product.attributes.get("vto_image_ready") is False:
                vto_image_ready = False

        if not vto_image_ready:
            return TryOnEligibilityResponse(
                supported=False,
                product_id=str(product.id),
                product_name=product.name,
                category=product.category,
                subcategory=product.subcategory,
                reason="Product image is not optimized for garment synthesis.",
                recommended_photo_type="none",
                product_image_url=product.image_url
            )

        # 5. Detect Clothing / Apparel
        is_clothing = (
            any(k in combined for k in cls.CLOTHING_KEYWORDS) or 
            cat_lower in ["apparel", "clothing"] or
            subcat_lower in ["jackets", "shirts", "t-shirts", "hoodies", "sweaters", "dresses", "shorts", "pants", "jeans", "trousers", "track pants", "sports bras"]
        )
        if is_clothing:
            return TryOnEligibilityResponse(
                supported=True,
                product_id=str(product.id),
                product_name=product.name,
                garment_type="CLOTHING",
                category=product.category,
                subcategory=product.subcategory or "Apparel",
                reason="Eligible for AI Clothing Virtual Try-On.",
                recommended_photo_type="full_body",
                product_image_url=product.image_url,
                color=product.attributes.get("color") if product.attributes else None,
                size=product.attributes.get("size") if product.attributes else None
            )

        # 5. Fallback unverified category
        return TryOnEligibilityResponse(
            supported=False,
            product_id=str(product.id),
            product_name=product.name,
            category=product.category,
            subcategory=product.subcategory,
            reason=f"Product '{product.name}' is not in an eligible clothing or footwear category.",
            recommended_photo_type="none",
            product_image_url=product.image_url
        )

    # -------------------------------------------------------------
    # 2. File Validation & Private Vault Storage
    # -------------------------------------------------------------

    @classmethod
    def validate_and_save_upload(cls, file_bytes: bytes, content_type: str) -> Tuple[bool, Optional[str], Optional[str]]:
        # Size limit check
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            return False, None, f"Uploaded file exceeds maximum allowed size of 10MB (got {len(file_bytes) / (1024*1024):.1f}MB)."

        if len(file_bytes) < 100:
            return False, None, "Uploaded file is empty or corrupted."

        # MIME type validation
        normalized_mime = (content_type or "").lower().split(";")[0].strip()
        if normalized_mime not in ALLOWED_MIME_TYPES:
            return False, None, f"Unsupported file type '{content_type}'. Allowed types: JPEG, PNG, WEBP."

        # Magic bytes verification
        valid_magic = False
        for expected in ALLOWED_MIME_TYPES[normalized_mime]:
            if file_bytes.startswith(expected):
                valid_magic = True
                break

        if not valid_magic:
            return False, None, "File content header does not match declared image format."

        # Save with cryptographically random internal key
        file_ext = ".jpg" if "jpeg" in normalized_mime else ".png" if "png" in normalized_mime else ".webp"
        internal_key = f"vto_input_{uuid.uuid4().hex}{file_ext}"
        storage_path = os.path.join(STORAGE_DIR, internal_key)

        try:
            with open(storage_path, "wb") as f:
                f.write(file_bytes)
            return True, internal_key, None
        except Exception as e:
            return False, None, f"Failed to store uploaded photo securely: {str(e)}"

    @classmethod
    def save_result_bytes(cls, result_bytes: bytes) -> str:
        internal_key = f"vto_result_{uuid.uuid4().hex}.jpg"
        storage_path = os.path.join(STORAGE_DIR, internal_key)
        with open(storage_path, "wb") as f:
            f.write(result_bytes)
        return internal_key

    @classmethod
    def get_media_path(cls, key: str) -> Optional[str]:
        # Path traversal guard
        safe_key = os.path.basename(key)
        full_path = os.path.join(STORAGE_DIR, safe_key)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            return full_path
        return None

    # -------------------------------------------------------------
    # 3. Job Execution & Lifecycle
    # -------------------------------------------------------------

    @classmethod
    def resolve_variant_garment(
        cls, product: Product, variant_id: Optional[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Resolves the exact variant garment image URL and canonical metadata.
        Strictly enforces variant integrity:
        - If a variant is specified, it MUST resolve to that exact variant's verified garment asset.
        - If the variant has no verified garment asset, raises ValueError("AI Try-On unavailable for this variant").
        - Never silently substitutes another color or default image.
        """
        attrs = product.attributes if (product.attributes and isinstance(product.attributes, dict)) else {}
        variant_details = attrs.get("variant_details") or attrs.get("variants") or {}
        variant_images = attrs.get("variant_images") or {}
        variant_vto_images = attrs.get("variant_vto_images") or {}

        resolved_color = None
        resolved_size = attrs.get("size")
        resolved_style_code = attrs.get("style_code") or product.model_number
        resolved_gtin = attrs.get("gtin") or product.gtin
        garment_img_url = None

        candidate_keys: List[str] = []
        if variant_id:
            raw_v = str(variant_id).strip()
            candidate_keys.append(raw_v)
            if "-" in raw_v and not raw_v.startswith("718833-"):
                candidate_keys.append(raw_v.split("-")[0].strip())
            if "/" in raw_v:
                candidate_keys.append(raw_v.split("/")[0].strip())
        else:
            if attrs.get("color"):
                candidate_keys.append(attrs.get("color").strip())

        # Deduplicate candidates while preserving order
        candidate_keys = list(dict.fromkeys([k for k in candidate_keys if k]))

        # 1. Check structured variant_details/variants map
        if candidate_keys and variant_details:
            for target_key in candidate_keys:
                matched_var = variant_details.get(target_key)
                if not matched_var:
                    for k, v in variant_details.items():
                        if (
                            k.lower() == target_key.lower()
                            or str(v.get("style_code", "")).lower() == target_key.lower()
                            or str(v.get("color", "")).lower() == target_key.lower()
                        ):
                            matched_var = v
                            break
                if matched_var:
                    resolved_color = matched_var.get("color", target_key)
                    resolved_size = matched_var.get("size", resolved_size)
                    resolved_style_code = matched_var.get("style_code", resolved_style_code)
                    resolved_gtin = matched_var.get("gtin", resolved_gtin)
                    garment_img_url = (
                        matched_var.get("vto_image_url")
                        or matched_var.get("garment_image_url")
                        or matched_var.get("image_url")
                    )
                    if garment_img_url:
                        break

        # 2. Check variant_vto_images or variant_images dictionaries
        if candidate_keys and not garment_img_url:
            for target_key in candidate_keys:
                if target_key in variant_vto_images and variant_vto_images[target_key]:
                    garment_img_url = variant_vto_images[target_key]
                    resolved_color = target_key
                    break
                elif target_key in variant_images and variant_images[target_key]:
                    garment_img_url = variant_images[target_key]
                    resolved_color = target_key
                    break
                else:
                    for k, v in variant_vto_images.items():
                        if k.lower() == target_key.lower() and v:
                            garment_img_url = v
                            resolved_color = k
                            break
                    if garment_img_url:
                        break
                    for k, v in variant_images.items():
                        if k.lower() == target_key.lower() and v:
                            garment_img_url = v
                            resolved_color = k
                            break
                    if garment_img_url:
                        break

        # 3. Check product default attributes if requested color matches product's primary color
        if candidate_keys and not garment_img_url:
            prod_color = (attrs.get("color") or "").lower().strip()
            prod_style = str(attrs.get("style_code") or product.model_number or "").lower().strip()
            for target_key in candidate_keys:
                tk_lower = target_key.lower().strip()
                if (prod_color and (tk_lower == prod_color or tk_lower in prod_color or prod_color in tk_lower)) or (prod_style and tk_lower == prod_style):
                    resolved_color = attrs.get("color") or target_key
                    resolved_style_code = attrs.get("style_code") or product.model_number
                    resolved_gtin = attrs.get("gtin") or product.gtin
                    garment_img_url = attrs.get("vto_image_url") or attrs.get("image_url") or product.image_url
                    if garment_img_url:
                        break

        # 4. If variant was 'standard'/'default'/size-only or matches default product asset
        is_generic_variant = (
            not variant_id
            or variant_id.lower().strip() in ["standard", "default", "primary", "none", ""]
            or variant_id.lower().strip() in ["s", "m", "l", "xl", "xxl", "small", "medium", "large"]
        )

        if is_generic_variant and not garment_img_url:
            garment_img_url = attrs.get("vto_image_url") or attrs.get("image_url") or product.image_url
            resolved_color = attrs.get("color") or "Standard"

        # 5. If a specific variant was requested but could NOT be resolved:
        if variant_id and not is_generic_variant and not garment_img_url:
            raise ValueError(f"AI Try-On unavailable for this variant ({variant_id}). No verified garment asset found.")

        # 6. If no variant specified, fallback to default product attributes if ready
        if not garment_img_url:
            garment_img_url = attrs.get("vto_image_url") or attrs.get("image_url") or product.image_url
            resolved_color = attrs.get("color") or "Standard"

        # Validate GTIN checksum if provided
        from app.services.price_intelligence.validators import validate_gtin_checksum
        is_gtin_valid = validate_gtin_checksum(resolved_gtin) if resolved_gtin else False
        canonical_gtin = resolved_gtin if is_gtin_valid else None

        resolved_meta = {
            "variant_id": variant_id or resolved_color,
            "color": resolved_color or attrs.get("color"),
            "size": resolved_size,
            "canonical_style_code": resolved_style_code,
            "style_code": resolved_style_code,
            "canonical_gtin": canonical_gtin,
            "gtin": canonical_gtin,
            "is_gtin_verified": is_gtin_valid,
            "is_style_code_verified": bool(resolved_style_code),
            "garment_asset": garment_img_url,
            "resolved_garment_asset": garment_img_url
        }

        return garment_img_url, resolved_meta

    @classmethod
    def create_and_execute_job(
        cls,
        db: Session,
        user_id: Optional[str],
        session_id: Optional[str],
        product_id: str,
        variant_id: Optional[str],
        file_bytes: bytes,
        content_type: str,
        consent_given: bool,
        background: bool = False
    ) -> VirtualTryOnJob:
        if not consent_given:
            raise ValueError("Explicit user consent is required before generating a virtual try-on preview.")

        # 1. Authoritative product lookup
        product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
        if not product:
            raise ValueError(f"Product '{product_id}' was not found in catalog.")

        # 2. Check eligibility
        eligibility = cls.is_virtual_tryon_supported(product)
        if not eligibility.supported:
            raise ValueError(eligibility.reason)

        # 3. Validate & save input photo
        valid, input_key, err = cls.validate_and_save_upload(file_bytes, content_type)
        if not valid or not input_key:
            raise ValueError(err or "Invalid image upload.")

        # 4. Resolve exact variant garment image & canonical style code
        garment_img_url, variant_meta = cls.resolve_variant_garment(product, variant_id)

        # 5. Select Provider & Create DB Record
        provider = VTOProviderRegistry.get_provider()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)

        job = VirtualTryOnJob(
            user_id=user_id,
            session_id=session_id,
            product_id=product.id,
            merchant_id=product.merchant_id,
            variant_id=variant_id,
            garment_type=TryOnGarmentType(eligibility.garment_type),
            provider=provider.provider_id,
            status=TryOnJobStatus.PROCESSING,
            progress_percent=5,
            processing_stage="PREPARING",
            progress_message="Preparing your photo...",
            sampling_step=None,
            sampling_total=None,
            input_image_key=input_key,
            product_image_url=garment_img_url,
            product_name_snapshot=product.name,
            variant_metadata=variant_meta,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            expires_at=expires_at
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Structured Audit Logging
        logger.info(
            f"[VTO_AUDIT] JobID={job.id} | ProductID={product.id} | SelectedVariant={variant_id} | "
            f"Color={variant_meta.get('color')} | StyleCode={variant_meta.get('style_code')} | "
            f"GarmentAsset={garment_img_url} | Category={eligibility.garment_type} | Provider={provider.provider_id}"
        )

        def do_inference(target_job_id: str, job_db: Session):
            j = job_db.query(VirtualTryOnJob).filter(VirtualTryOnJob.id == target_job_id).first()
            if not j:
                return

            def on_progress(stage: str, percent: int, step: Optional[int], total: Optional[int], msg: str):
                try:
                    cur_pct = getattr(j, "progress_percent", 0) or 0
                    clamped_pct = max(cur_pct, min(100, int(percent)))
                    j.progress_percent = clamped_pct
                    j.processing_stage = stage
                    j.progress_message = msg
                    if step is not None:
                        j.sampling_step = step
                    if total is not None:
                        j.sampling_total = total
                    job_db.commit()
                except Exception as ex:
                    logger.warning(f"Error updating VTO progress: {ex}")

            product_meta = {
                "name": j.product_name_snapshot,
                "brand": (j.product.brand if j.product else "Apex") or "Apex",
                "category": j.garment_type.value,
                "variant": j.variant_id or (j.variant_metadata.get("color") if j.variant_metadata else ""),
                "style_code": j.variant_metadata.get("style_code") if j.variant_metadata else None,
                "color": j.variant_metadata.get("color") if j.variant_metadata else None
            }

            try:
                success, res_bytes, err_code, err_msg = provider.generate_try_on(
                    person_image_bytes=file_bytes,
                    product_image_url=j.product_image_url,
                    garment_type=j.garment_type.value,
                    product_metadata=product_meta,
                    progress_callback=on_progress
                )

                if success and res_bytes:
                    if res_bytes == file_bytes:
                        j.status = TryOnJobStatus.FAILED
                        j.processing_stage = "FAILED"
                        j.error_code = "IDENTICAL_OUTPUT_REJECTED"
                        j.error_message = "Synthesized visual output was rejected because it returned an unmodified input photo."
                    else:
                        result_key = cls.save_result_bytes(res_bytes)
                        j.result_image_key = result_key
                        j.status = TryOnJobStatus.COMPLETED
                        j.progress_percent = 100
                        j.processing_stage = "COMPLETED"
                        j.progress_message = "Try-on ready"
                        j.completed_at = datetime.now(timezone.utc)
                else:
                    j.status = TryOnJobStatus.FAILED
                    j.processing_stage = "FAILED"
                    j.error_code = err_code or "GENERATION_FAILED"
                    j.error_message = err_msg or "Failed to synthesize try-on visual."

                job_db.commit()
                job_db.refresh(j)

                # Record Analytics Event
                event = VirtualTryOnEvent(
                    job_id=j.id,
                    merchant_id=j.merchant_id,
                    user_id=j.user_id,
                    product_id=j.product_id,
                    event_type="VTO_COMPLETED" if j.status == TryOnJobStatus.COMPLETED else "VTO_FAILED",
                    category=j.garment_type.value
                )
                job_db.add(event)
                job_db.commit()

            except Exception as e:
                logger.error(f"Inference exception for job {target_job_id}: {e}")
                j.status = TryOnJobStatus.FAILED
                j.processing_stage = "FAILED"
                j.error_code = "VTO_UNEXPECTED_ERROR"
                j.error_message = f"An unexpected error occurred: {str(e)}"
                job_db.commit()

        if background:
            import threading
            from app.database.session import SessionLocal
            def bg_runner():
                bg_db = SessionLocal()
                try:
                    do_inference(job.id, bg_db)
                finally:
                    bg_db.close()
            t = threading.Thread(target=bg_runner, daemon=True)
            t.start()
        else:
            do_inference(job.id, db)

        return job

    # -------------------------------------------------------------
    # 4. Style Engine ("Complete the Look")
    # -------------------------------------------------------------

    @classmethod
    def get_style_recommendations(cls, db: Session, job: VirtualTryOnJob) -> List[StyleRecommendationItem]:
        product = db.query(Product).filter(Product.id == job.product_id).first()
        if not product:
            return []

        # Find complementary products from same merchant
        recommendations: List[StyleRecommendationItem] = []
        is_footwear = job.garment_type == TryOnGarmentType.FOOTWEAR

        if is_footwear:
            # Recommend running shorts or athletic tee
            pairs = db.query(Product).filter(
                Product.merchant_id == job.merchant_id,
                Product.is_active == True,
                Product.id != job.product_id,
                Product.category.in_(["Apparel", "Fashion", "Sports & Fitness"])
            ).limit(3).all()

            for p in pairs:
                recommendations.append(StyleRecommendationItem(
                    product_id=str(p.id),
                    name=p.name,
                    brand=p.brand,
                    price=float(p.price),
                    mrp=float(p.mrp) if p.mrp else None,
                    category=p.category,
                    subcategory=p.subcategory,
                    image_url=p.image_url,
                    styling_reason=f"Pairs seamlessly with your {product.name} for high-performance training."
                ))
        else:
            # Recommend matching footwear
            shoes = db.query(Product).filter(
                Product.merchant_id == job.merchant_id,
                Product.is_active == True,
                Product.id != job.product_id,
                Product.category.in_(["Footwear", "Running"])
            ).limit(3).all()

            for p in shoes:
                recommendations.append(StyleRecommendationItem(
                    product_id=str(p.id),
                    name=p.name,
                    brand=p.brand,
                    price=float(p.price),
                    mrp=float(p.mrp) if p.mrp else None,
                    category=p.category,
                    subcategory=p.subcategory,
                    image_url=p.image_url,
                    styling_reason=f"Completes the outfit with lightweight matching footwear."
                ))

        return recommendations

    # -------------------------------------------------------------
    # 5. Merchant Readiness Analytics (Zero Customer Media Access)
    # -------------------------------------------------------------

    @classmethod
    def get_merchant_readiness_stats(cls, db: Session, merchant_id: str) -> MerchantVTOStatsResponse:
        products = db.query(Product).filter(Product.merchant_id == merchant_id, Product.is_active == True).all()
        total_p = len(products)
        eligible_items = []
        eligible_count = 0

        for p in products:
            elig = cls.is_virtual_tryon_supported(p)
            status_label = "READY" if elig.supported else "UNSUPPORTED_CATEGORY"
            if not p.image_url:
                status_label = "MISSING_IMAGE"

            if elig.supported:
                eligible_count += 1

            eligible_items.append(MerchantVTOReadinessItem(
                product_id=str(p.id),
                name=p.name,
                brand=p.brand,
                category=p.category,
                subcategory=p.subcategory,
                image_url=p.image_url,
                vto_status=status_label,
                garment_type=elig.garment_type
            ))

        readiness_pct = round((eligible_count / total_p * 100), 1) if total_p > 0 else 0.0

        # Aggregate event counts
        events = db.query(VirtualTryOnEvent).filter(VirtualTryOnEvent.merchant_id == merchant_id).all()
        started = len([e for e in events if e.event_type in ["STARTED", "COMPLETED", "FAILED"]])
        completed = len([e for e in events if e.event_type == "COMPLETED"])
        add_to_cart = len([e for e in events if e.event_type == "ADD_TO_CART"])
        comp_rate = round((completed / started * 100), 1) if started > 0 else 100.0

        return MerchantVTOStatsResponse(
            total_products=total_p,
            vto_eligible_products=eligible_count,
            vto_readiness_percentage=readiness_pct,
            total_tryons_started=started,
            total_tryons_completed=completed,
            completion_rate_percentage=comp_rate,
            add_to_cart_after_tryon_count=add_to_cart,
            items=eligible_items
        )
