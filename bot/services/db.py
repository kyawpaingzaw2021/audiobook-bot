"""Database engine + async session factory."""
import logging

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.config import config
from bot.models import Base  # noqa: F401

logger = logging.getLogger(__name__)


engine = create_async_engine(
    config.db_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=30,
    connect_args={
        "server_settings": {
            "application_name": "audiobook_bot",
        },
    },
)


SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB initialized.")


async def close_db() -> None:
    """Dispose engine on shutdown."""
    await engine.dispose()
    logger.info("DB engine closed.")
