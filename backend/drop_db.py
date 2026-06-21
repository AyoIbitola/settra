import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS payments CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS payment_targets CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS invoices CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE;"))
        await conn.execute(text("DROP TYPE IF EXISTS invoice_status CASCADE;"))
    await engine.dispose()

asyncio.run(main())
