"""Application configuration via Pydantic Settings, loaded from environment / .env file."""

from pydantic_settings import BaseSettings


# Default networks per stablecoin — configured here, not hardcoded inline.
# USDC on BASE (low fees, EVM compatible), USDT on TRX (Tron, lowest fees).
# Revisit in v2 to expose UI network selection.
DEFAULT_NETWORKS: dict[str, str] = {
    "usdc": "BASE",
    "usdt": "TRX",
    "btc_onchain": "BTC",
}

# All confirmed networks per currency (PRD Section 5.3).
# Used to validate incoming 'network' values — reject anything not in this set.
SUPPORTED_NETWORKS: dict[str, set[str]] = {
    "usdc": {"BASE", "ETH", "TRX", "XLM", "SOL"},
    "usdt": {"BSC", "ETH", "TRX", "SOL"},
    "btc_onchain": {"BTC"},
}


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/invoicing"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Busha — no hardcoded default for BASE_URL.
    # Operator MUST set this explicitly to control which environment is active:
    #   Sandbox:    https://api.sandbox.busha.so
    #   Production: [CONFIRM from dashboard — see PRD Section 16 item 6]
    BUSHA_BASE_URL: str
    BUSHA_SECRET_KEY: str = ""
    BUSHA_WEBHOOK_SECRET: str = ""
    BUSHA_PUBLIC_KEY: str = ""

    # Auth
    JWT_SECRET: str = "change-me-to-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60

    # Email (Resend)
    RESEND_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "receipts@yourapp.com"

    # Receipt storage — local filesystem for dev, S3-compatible path for prod
    RECEIPTS_DIR: str = "receipts"   # local path when ENVIRONMENT=development
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET_NAME: str = ""

    # App
    APP_BASE_URL: str = "http://localhost:8000"
    FRONTEND_BASE_URL: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"  # development | staging | production

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
