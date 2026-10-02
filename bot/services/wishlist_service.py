"""Wishlist service — race-safe add/remove."""
import logging

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.wishlist import Wishlist

logger = logging.getLogger(__name__)


async def add(
    session: AsyncSession, user_id: int, book_id: int
) -> bool:
    """Add to wishlist. Race-safe. Returns True if added."""
    w = Wishlist(user_id=user_id, book_id=book_id)
    session.add(w)

    try:
        await session.commit()
        return True
    except IntegrityError:
        await session.rollback()
        return False


async def remove(
    session: AsyncSession, user_id: int, book_id: int
) -> bool:
    """Remove from wishlist. Returns True if removed."""
    r = await session.execute(
        delete(Wishlist).where(
            Wishlist.user_id == user_id,
            Wishlist.book_id == book_id,
        )
    )
    await session.commit()
    return (r.rowcount or 0) > 0


async def toggle(
    session: AsyncSession, user_id: int, book_id: int
) -> bool:
    """Toggle wishlist. Returns True if now in wishlist."""
    if await is_wished(session, user_id, book_id):
        await remove(session, user_id, book_id)
        return False
    await add(session, user_id, book_id)
    return True


async def is_wished(
    session: AsyncSession, user_id: int, book_id: int
) -> bool:
    """Check if user has book in wishlist."""
    r = await session.execute(
        select(Wishlist.id)
        .where(
            Wishlist.user_id == user_id,
            Wishlist.book_id == book_id,
        )
        .limit(1)
    )
    return r.scalar_one_or_none() is not None


async def list_user(
    session: AsyncSession, user_id: int
) -> list[int]:
    """Book IDs in user's wishlist (newest first)."""
    r = await session.execute(
        select(Wishlist.book_id)
        .where(Wishlist.user_id == user_id)
        .order_by(Wishlist.created_at.desc())
    )
    return [row[0] for row in r.all()]


async def list_watchers(
    session: AsyncSession, book_id: int
) -> list[int]:
    """User IDs watching a book."""
    r = await session.execute(
        select(Wishlist.user_id).where(
            Wishlist.book_id == book_id
        )
    )
    return [row[0] for row in r.all()]


async def count_for_book(
    session: AsyncSession, book_id: int
) -> int:
    """Count wishlist entries for a book."""
    from sqlalchemy import func

    r = await session.execute(
        select(func.count(Wishlist.id)).where(
            Wishlist.book_id == book_id
        )
    )
    return int(r.scalar() or 0)
