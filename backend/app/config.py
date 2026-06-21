"""Application configuration via Pydantic Settings, loaded from environment / .env file."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/invoicing"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Bitnob
    BITNOB_BASE_URL: str = "https://sandboxapi.bitnob.co"
    BITNOB_CLIENT_ID: str = ""
    BITNOB_CLIENT_SECRET: str = ""
    BITNOB_WEBHOOK_SECRET: str = ""

    # Auth
    JWT_SECRET: str = "change-me-to-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60

    # Email (Resend)
    RESEND_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "receipts@yourapp.com"

    # AWS S3 (Receipts)
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
