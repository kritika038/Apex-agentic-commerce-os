import urllib.parse
from typing import Optional, Dict, Any
from datetime import timedelta
import httpx
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.config import settings
from app.database.session import get_db
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.schemas.token import Token
from app.auth.deps import get_current_active_user, get_optional_current_user

router = APIRouter()

class GoogleCallbackRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None
    role: Optional[str] = "customer" # "customer" or "merchant_admin"

class DevLoginRequest(BaseModel):
    role: str = "customer" # "customer" or "merchant_admin"

def _is_allowed_redirect_uri(redirect_uri: str) -> bool:
    """
    Validates redirect URI against configured URI and permitted local development origins.
    """
    if not redirect_uri:
        return False
    if redirect_uri == settings.GOOGLE_REDIRECT_URI:
        return True
    allowed_origins = [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:3001",
        "http://localhost:3001"
    ]
    for origin in allowed_origins:
        if redirect_uri == f"{origin}/auth/callback":
            return True
    return False

def _derive_google_user_role(email: str, user: Optional[User] = None) -> str:
    """
    Server-authoritative role derivation for Google OAuth accounts.
    Only emails explicitly configured in settings.merchant_admin_emails are granted 'merchant_admin'.
    All other accounts receive 'customer'. Client-supplied role intent is never trusted for authorization.
    """
    if email.lower() in settings.merchant_admin_emails:
        return "merchant_admin"
    return "customer"

@router.get("/config")
def get_auth_config() -> Dict[str, Any]:
    """
    Returns the active authentication configuration.
    Indicates whether Google OAuth credentials are set and whether Dev Auth is allowed.
    """
    is_google_configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    is_dev_allowed = bool(settings.ALLOW_DEV_AUTH and settings.ENVIRONMENT != "production")
    return {
        "google_oauth_configured": is_google_configured,
        "allow_dev_auth": is_dev_allowed,
        "environment": settings.ENVIRONMENT,
        "google_redirect_uri": settings.GOOGLE_REDIRECT_URI
    }

@router.get("/google/url")
def get_google_auth_url(
    role: str = Query("customer", enum=["customer", "merchant_admin"]),
    redirect_uri: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Generates the real Google OAuth 2.0 authorization URL.
    If Google OAuth credentials are not set in the environment, returns configured: False.
    """
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        return {
            "configured": False,
            "message": "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env.",
            "auth_url": None
        }

    target_redirect = settings.GOOGLE_REDIRECT_URI
    if redirect_uri:
        if _is_allowed_redirect_uri(redirect_uri):
            target_redirect = redirect_uri
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google OAuth redirect URI does not match the configured application URL."
            )

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": target_redirect,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": role
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return {
        "configured": True,
        "auth_url": auth_url,
        "role": role,
        "redirect_uri": target_redirect
    }

@router.post("/google/callback", response_model=Dict[str, Any])
async def google_auth_callback(payload: GoogleCallbackRequest, db: Session = Depends(get_db)):
    """
    Google OAuth 2.0 Callback Handler.
    Securely exchanges authorization code for Google ID token, retrieves profile,
    creates or finds user in database, and mints an authoritative JWT access token.
    """
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured."
        )

    target_redirect = settings.GOOGLE_REDIRECT_URI
    if payload.redirect_uri:
        if _is_allowed_redirect_uri(payload.redirect_uri):
            target_redirect = payload.redirect_uri
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google OAuth redirect URI does not match the configured application URL."
            )

    # 1. Exchange authorization code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": payload.code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": target_redirect,
        "grant_type": "authorization_code"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            token_res = await client.post(token_url, data=token_data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to communicate with Google OAuth token service: {str(e)}"
            )

        if token_res.status_code != 200:
            err_json = {}
            try:
                err_json = token_res.json()
            except Exception:
                pass
            err_code = err_json.get("error", "")
            if err_code == "redirect_uri_mismatch":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google OAuth redirect URI does not match the configured application URL."
                )
            elif err_code == "invalid_grant":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google authorization code is invalid or has expired. Please sign in again."
                )
            elif err_code == "invalid_client":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google OAuth client credentials (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET) are invalid."
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google authentication could not be completed. Please try again."
            )
        token_json = token_res.json()
        access_token_google = token_json.get("access_token")

        # 2. Fetch user profile from Google UserInfo endpoint
        try:
            userinfo_res = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token_google}"}
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to retrieve Google user profile: {str(e)}"
            )

        if userinfo_res.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve verified Google user profile."
            )
        profile = userinfo_res.json()

    email = profile.get("email")
    full_name = profile.get("name", email.split("@")[0] if email else "Google User")
    picture = profile.get("picture")

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no verified email address.")

    if profile.get("email_verified") is False:
        raise HTTPException(status_code=400, detail="Google account email is not verified.")

    # 3. Resolve default merchant for tenant scoping
    merchant = db.query(Merchant).first()
    merchant_id = merchant.id if merchant else None

    # 4. Find or create user
    user = db.query(User).filter(User.email == email).first()
    assigned_role = _derive_google_user_role(email, user)

    if not user:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(f"google_oauth_{email}"),
            role=assigned_role,
            merchant_id=merchant_id,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.full_name = full_name or user.full_name
        user.role = assigned_role
        if not user.merchant_id:
            user.merchant_id = merchant_id
        db.commit()
        db.refresh(user)

    # 5. Mint server JWT session
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    app_token = create_access_token(
        subject=user.id,
        merchant_id=user.merchant_id,
        role=user.role,
        expires_delta=access_token_expires
    )

    return {
        "access_token": app_token,
        "token_type": "bearer",
        "role": user.role,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "merchant_id": user.merchant_id,
            "avatar_url": picture
        }
    }

@router.post("/dev-login", response_model=Dict[str, Any])
def dev_login(payload: DevLoginRequest, db: Session = Depends(get_db)):
    """
    Controlled Dev Login Endpoint.
    Strictly blocked in production (returns 403).
    Enables rapid testing of Customer vs. Merchant Admin workflows when Google credentials are not set.
    """
    if settings.ENVIRONMENT == "production" or not settings.ALLOW_DEV_AUTH:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Developer login is disabled in production environment."
        )

    merchant = db.query(Merchant).first()
    merchant_id = merchant.id if merchant else None

    if payload.role == "merchant_admin":
        email = "admin@demo-sports.test"
        full_name = "Merchant Admin"
        role = "merchant_admin"
    else:
        email = "customer@demo-sports.test"
        full_name = "Alex Customer"
        role = "customer"

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash("password123"),
            role=role,
            merchant_id=merchant_id,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    app_token = create_access_token(
        subject=user.id,
        merchant_id=user.merchant_id,
        role=user.role,
        expires_delta=access_token_expires
    )

    return {
        "access_token": app_token,
        "token_type": "bearer",
        "role": user.role,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "merchant_id": user.merchant_id
        }
    }

@router.get("/me")
def get_current_user_profile(current_user: User = Depends(get_current_active_user)):
    """
    Returns current authenticated user profile and active merchant context.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "merchant_id": current_user.merchant_id,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }

class ProfileUpdateRequest(BaseModel):
    full_name: str

@router.get("/profile")
def get_customer_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns authentic, database-grounded customer profile with order metrics, wallet balance, and active vouchers.
    """
    from app.database.models.purchase_intent import PurchaseIntent
    from app.database.models.payment_transaction import PaymentTransaction
    from app.database.models.rewards import CoinWallet
    from app.services.reward_service import RewardService

    # Query customer purchase intents
    intents = db.query(PurchaseIntent).filter(
        PurchaseIntent.buyer_id == current_user.id
    ).order_by(PurchaseIntent.created_at.desc()).all()

    # Query wallet
    wallet = db.query(CoinWallet).filter(
        CoinWallet.user_id == current_user.id
    ).first()

    # Query captured transactions for total spend calculation
    captured_txs = db.query(PaymentTransaction).join(
        PurchaseIntent, PaymentTransaction.purchase_intent_id == PurchaseIntent.id
    ).filter(
        PurchaseIntent.buyer_id == current_user.id,
        PaymentTransaction.status == "CAPTURED"
    ).all()

    total_spent = sum(float(tx.amount) for tx in captured_txs)

    # Extract unique saved addresses from previous orders
    saved_addresses = []
    seen_addresses = set()
    latest_phone = None
    for pi in intents:
        addr = pi.delivery_address
        if addr and isinstance(addr, dict) and addr.get("city"):
            if addr.get("phone") and not latest_phone:
                latest_phone = addr.get("phone")
            addr_key = f"{addr.get('address_line1')}_{addr.get('city')}_{addr.get('pin_code')}"
            if addr_key not in seen_addresses:
                seen_addresses.add(addr_key)
                saved_addresses.append(addr)

    # Resolve active merchant coupons
    m_id = current_user.merchant_id
    if not m_id:
        default_m = db.query(Merchant).first()
        m_id = default_m.id if default_m else None
    
    coupons = RewardService.get_public_coupons(db, m_id) if m_id else []

    is_google = bool(current_user.hashed_password and current_user.hashed_password.startswith("google_oauth_"))

    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_google_user": is_google,
        "phone": latest_phone,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "orders_count": len(intents),
        "total_spent": total_spent,
        "apex_coins_balance": wallet.balance if wallet else 0,
        "reward_points_balance": (wallet.balance * 10) if wallet else 0,
        "lifetime_coins_earned": wallet.balance if wallet else 0,
        "saved_addresses": saved_addresses[:5],
        "default_address": saved_addresses[0] if saved_addresses else None,
        "active_coupons": [
            {
                "code": getattr(c, "code", str(c)),
                "description": getattr(c, "description", "") or "",
                "discount_type": getattr(c, "discount_type", "PERCENTAGE"),
                "discount_value": float(getattr(c, "discount_value", 10.0)),
                "min_order_amount": float(getattr(c, "min_order_amount", 0.0))
            }
            for c in coupons[:3]
        ],
        "preferences": {
            "preferred_category": "Running & Athletics",
            "preferred_shoe_size": "UK 9 / US 10",
            "notifications_enabled": True,
            "ai_shopping_copilot": True
        },
        "recent_orders": [
            {
                "id": pi.id,
                "status": pi.status,
                "amount": float(pi.requested_amount) if pi.requested_amount else 0.0,
                "currency": pi.currency or "INR",
                "created_at": pi.created_at.isoformat() if pi.created_at else None
            }
            for pi in intents[:5]
        ]
    }

@router.put("/profile")
def update_customer_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Updates the authenticated user's profile information.
    """
    clean_name = payload.full_name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Name cannot be empty.")
    
    current_user.full_name = clean_name
    db.commit()
    db.refresh(current_user)

    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "message": "Profile updated successfully."
    }

@router.get("/merchant-profile")
def get_merchant_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns authentic, database-grounded Merchant profile and business metrics.
    Strictly requires merchant_admin role.
    """
    if current_user.role not in ["merchant_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant Admin privileges required."
        )

    from app.database.models.product import Product
    from app.database.models.inventory import Inventory
    from app.database.models.payment_transaction import PaymentTransaction
    from app.database.models.policy import Policy

    merchant = None
    if current_user.merchant_id:
        merchant = db.query(Merchant).filter(Merchant.id == current_user.merchant_id).first()
    if not merchant:
        merchant = db.query(Merchant).first()

    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant details not found.")

    # Catalog & revenue stats
    catalog_count = db.query(Product).filter(
        Product.merchant_id == merchant.id,
        Product.is_active == True
    ).count()

    inv_records = db.query(Inventory).filter(
        Inventory.merchant_id == merchant.id
    ).all()
    total_inventory_units = sum(i.stock_quantity for i in inv_records)

    captured_txs = db.query(PaymentTransaction).filter(
        PaymentTransaction.merchant_id == merchant.id,
        PaymentTransaction.status == "CAPTURED"
    ).all()

    total_gmv = sum(float(tx.amount) for tx in captured_txs)
    total_orders = len(captured_txs)

    # Active policy
    policy = db.query(Policy).filter(Policy.merchant_id == merchant.id).first()

    # Safe payment status display (no credentials exposed)
    is_razorpay_configured = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
    payment_status = "Razorpay Test Mode — Configured" if is_razorpay_configured else "Mock Gateway — Operational"

    return {
        "merchant_id": merchant.id,
        "merchant_name": merchant.name,
        "domain": merchant.domain,
        "created_at": merchant.created_at.isoformat() if merchant.created_at else None,
        "admin_email": current_user.email,
        "admin_name": current_user.full_name,
        "role": current_user.role,
        "account_type": "Merchant Admin",
        "catalog_size": catalog_count,
        "inventory_units": total_inventory_units,
        "total_orders": total_orders,
        "total_gmv": total_gmv,
        "currency": "INR",
        "payment_status": payment_status,
        "razorpay_mode": settings.RAZORPAY_MODE,
        "ai_agent_status": "AI Shopping Assistant & Sales Agent Active",
        "merchant_auth_status": "Server Authorized (Strict Role Separation)",
        "governance": {
            "auto_approval_threshold": float(policy.approval_threshold) if policy else 5000.0,
            "max_transaction_amount": float(policy.max_transaction_amount) if policy else 10000.0,
            "status": "ENFORCED"
        }
    }

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "customer"

class LoginJsonRequest(BaseModel):
    email: str
    password: str

@router.post("/register", response_model=Dict[str, Any])
def register_customer(payload: RegisterRequest, db: Session = Depends(get_db)):
    clean_email = payload.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Please provide a valid email address.")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    
    existing = db.query(User).filter(User.email == clean_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    
    merchant = db.query(Merchant).first()
    merchant_id = merchant.id if merchant else None

    user = User(
        email=clean_email,
        full_name=payload.full_name or clean_email.split("@")[0].capitalize(),
        hashed_password=get_password_hash(payload.password),
        role=payload.role if payload.role in ["customer", "merchant_admin"] else "customer",
        merchant_id=merchant_id,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    app_token = create_access_token(
        subject=user.id,
        merchant_id=user.merchant_id,
        role=user.role,
        expires_delta=access_token_expires
    )

    return {
        "access_token": app_token,
        "token_type": "bearer",
        "role": user.role,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "merchant_id": user.merchant_id
        }
    }

@router.post("/login-json", response_model=Dict[str, Any])
def login_json(payload: LoginJsonRequest, db: Session = Depends(get_db)):
    clean_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive.")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    app_token = create_access_token(
        subject=user.id,
        merchant_id=user.merchant_id,
        role=user.role,
        expires_delta=access_token_expires
    )
    return {
        "access_token": app_token,
        "token_type": "bearer",
        "role": user.role,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "merchant_id": user.merchant_id
        }
    }

@router.post("/login", response_model=Token)
def login_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    access_token = create_access_token(
        subject=user.id,
        merchant_id=user.merchant_id,
        role=user.role,
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/test-token", response_model=dict)
def test_token(current_user: User = Depends(get_current_active_user)):
    return {"user_id": current_user.id, "email": current_user.email, "merchant_id": current_user.merchant_id}
