"""FastAPI application instantiation and router wiring."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.routers import auth, invoices, overpayment_credits, public, webhooks

# Shared limiter instance — imported by routers that need it
limiter = Limiter(key_func=get_remote_address)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Invoicing Platform API",
        version="0.1.0",
        description="Bitcoin and Stablecoin Invoicing Backend",
    )

    # Attach slowapi limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.ENVIRONMENT == "development" else [settings.FRONTEND_BASE_URL],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(auth.router)
    app.include_router(invoices.router)
    app.include_router(overpayment_credits.router)
    app.include_router(public.router)
    app.include_router(webhooks.router)

    return app


app = create_app()


@app.get("/health", tags=["Health"])
async def health(request: Request):
    """
    Health check — verifies DB and Redis connectivity.
    Required by hosting platforms (Railway, Render, Fly.io) for process supervision.
    """
    from app.db import async_session_factory
    from sqlalchemy import text
    import redis.asyncio as aioredis

    results = {"status": "ok", "db": "ok", "redis": "ok"}

    # Check DB
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        results["db"] = f"error: {exc}"
        results["status"] = "degraded"

    # Check Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
    except Exception as exc:
        results["redis"] = f"error: {exc}"
        results["status"] = "degraded"

    return results
