from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Agentic Commerce OS"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development" # "development", "test", "demo", "production"
    
    # Security
    SECRET_KEY: str = "supersecretjwtkeythatshouldbechangedinproduction"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8 # 8 days
    
    # Database
    DATABASE_URL: str = "sqlite:///./commerce_os.db"
    
    # Payment Provider Configuration
    PAYMENT_PROVIDER: str = "mock" # "razorpay" or "mock"
    RAZORPAY_MODE: str = "test"    # strictly "test", never "live" in demo
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Google OAuth 2.0 Configuration
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:3000/auth/callback"
    ALLOW_DEV_AUTH: bool = True # Enabled for dev/demo; blocked in production
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
    MERCHANT_ADMIN_EMAILS: str = ""
    
    # AI Provider
    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: str = ""

    # Amazon Creators API Configuration
    AMAZON_CREATORS_API_ENABLED: bool = False
    AMAZON_CLIENT_ID: str = ""
    AMAZON_CLIENT_SECRET: str = ""
    AMAZON_PARTNER_TAG: str = ""
    AMAZON_MARKETPLACE: str = "www.amazon.in"
    AMAZON_CREATORS_API_HOST: str = "webservices.amazon.in"

    # Virtual Try-On Configuration
    VIRTUAL_TRYON_ENABLED: bool = True
    VIRTUAL_TRYON_PROVIDER: str = "huggingface_zerogpu" # "huggingface_zerogpu", "local_fashn", "fashn", "demo"
    VTO_HF_SPACE_URL: str = "https://kritika68-apex-vton.hf.space"
    HF_TOKEN: str = ""
    FASHN_API_KEY: str = ""
    FASHN_API_BASE_URL: str = "https://api.fashn.ai/v1"
    FASHN_MODEL_NAME: str = "tryon-v1.6"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def merchant_admin_emails(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.MERCHANT_ADMIN_EMAILS.split(",")
            if email.strip()
        }

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
