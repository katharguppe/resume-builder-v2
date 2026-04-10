import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_EXTRACT_MODEL: str = os.getenv("LLM_EXTRACT_MODEL", "claude-haiku-4-5-20251001")
    LLM_REWRITE_MODEL: str = os.getenv("LLM_REWRITE_MODEL", "claude-sonnet-4-6")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    LIBREOFFICE_PATH: str = os.getenv("LIBREOFFICE_PATH", "soffice")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MAX_LLM_RETRIES: int = int(os.getenv("MAX_LLM_RETRIES", "3"))
    BEST_PRACTICE_MAX_TOKENS: int = int(os.getenv("BEST_PRACTICE_MAX_TOKENS", "3000"))

config = Config()
