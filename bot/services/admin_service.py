"""Admin service — check + ensure super admin."""
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import config
from bot.models.admin import Admin

logger = logging.getLogger(__name__)

_CACHE: dict[int, tuple[bool, float]] = {}
_CACHE_TTL = 300.0


def _cache_get(tg_id: int) -> bool | None:
    entry = _CACHE.get(tg_id)
    if entry is None:
        return None
    ok, ts = entry
    if time.time() - ts > _CACHE_TTL:
        _CACHE.pop(tg_id, None)
        return None
    return ok


def _cache_set(tg_id: int, ok: bool) -> None:
    _CACHE[tg_id] = (ok, time.time())


def clear_cache(tg_id: int | None = None) -> None:
    """Clear admin cache (call when admins change)."""
    if tg_id is None:
        _CACHE.clear()
    else:
        _CACHE.pop(tg_id, None)


async def is_admin(session: AsyncSession, tg_id: int) -> bool:
    """Super admin (env) or active DB admin. Cached 5 min."""
    if config.ADMIN_ID != 0 and tg_id == config.ADMIN_ID:
        return True

    cached = _cache_get(tg_id)
    if cached is not None:
        return cached

    r = await session.execute(
        select(Admin).where(
            Admin.tg_id == tg_id,
            Admin.is_active == True,  # noqa: E712
        )
    )
    ok = r.scalar_one_or_none() is not None
    _cache_set(tg_id, ok)
    return ok


async def ensure_super_admin(session: AsyncSession) -> None:
    """Idempotently ensure env super admin exists in DB."""
    if config.ADMIN_ID == 0:
        return

    r = await session.execute(
        select(Admin).where(Admin.tg_id == config.ADMIN_ID)
    )
    admin = r.scalar_one_or_none()

    if admin is None:
        session.add(Admin(
            tg_id=config.ADMIN_ID,
            role="super",
            is_active=True,
        ))
        await session.commit()
        logger.info(f"Super admin created: {config.ADMIN_ID}")


async def add_admin(
    session: AsyncSession,
    tg_id: int,
    added_by: int,
    role: str = "admin",
) -> Admin | None:
    """Add a new DB admin."""
    r = await session.execute(
        select(Admin).where(Admin.tg_id == tg_id)
    )
    existing = r.scalar_one_or_none()

    if existing is not None:
        if not existing.is_active:
            existing.is_active = True
            await session.commit()
            clear_cache(tg_id)
        return existing

    admin = Admin(
        tg_id=tg_id,
        role=role,
        is_active=True,
        added_by=added_by,
    )
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    clear_cache(tg_id)
    logger.info(f"Admin added: {tg_id} by {added_by}")
    return admin


async def remove_admin(
    session: AsyncSession, tg_id: int
) -> bool:
    """Deactivate a DB admin (cannot remove env super admin)."""
    if tg_id == config.ADMIN_ID:
        return False

    r = await session.execute(
        select(Admin).where(Admin.tg_id == tg_id)
    )
    admin = r.scalar_one_or_none()
    if admin is None:
        return False

    admin.is_active = False
    await session.commit()
    clear_cache(tg_id)
    logger.info(f"Admin removed: {tg_id}")
    return True


async def list_admins(session: AsyncSession) -> list[Admin]:
    """List all active admins."""
    r = await session.execute(
        select(Admin)
        .where(Admin.is_active == True)  # noqa: E712
        .order_by(Admin.created_at)
    )
    return list(r.scalars().all())
