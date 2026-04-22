import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    # LLM
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    # LLM provider selection (claude | gemini | deepseek)
    LLM_EXTRACT_PROVIDER: str = os.getenv("LLM_EXTRACT_PROVIDER", "claude")
    LLM_REWRITE_PROVIDER: str = os.getenv("LLM_REWRITE_PROVIDER", "claude")
    # Provider API keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    LLM_EXTRACT_MODEL: str = os.getenv("LLM_EXTRACT_MODEL", "claude-haiku-4-5-20251001")
    LLM_REWRITE_MODEL: str = os.getenv("LLM_REWRITE_MODEL", "claude-sonnet-4-6")
    LLM_GEMINI_EXTRACT_MODEL: str = os.getenv("LLM_GEMINI_EXTRACT_MODEL", "gemini-2.0-flash")
    LLM_DEEPSEEK_REWRITE_MODEL: str = os.getenv("DEEPSEEK_REWRITE_MODEL", "deepseek-chat")
    # Crypto
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    # LibreOffice
    LIBREOFFICE_PATH: str = os.getenv("LIBREOFFICE_PATH", "soffice")
    # Logging / LLM tuning
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MAX_LLM_RETRIES: int = int(os.getenv("MAX_LLM_RETRIES", "3"))
    BEST_PRACTICE_MAX_TOKENS: int = int(os.getenv("BEST_PRACTICE_MAX_TOKENS", "3000"))
    # SMTP (OTP delivery)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD_ENCRYPTED: str = os.getenv("SMTP_PASSWORD_ENCRYPTED", "")
    # Auth
    OTP_EXPIRY_MINUTES: int = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))
    SESSION_EXPIRY_HOURS: int = int(os.getenv("SESSION_EXPIRY_HOURS", "24"))
    # Payment
    PAYMENT_PROVIDER: str = os.getenv("PAYMENT_PROVIDER", "razorpay")
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    RESUME_DOWNLOAD_PRICE_INR: int = int(os.getenv("RESUME_DOWNLOAD_PRICE_INR", "99"))
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:8501")

config = Config()
