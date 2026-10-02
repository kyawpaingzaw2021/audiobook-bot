"""Rating service — upsert + summary."""
import logging

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.purchase import Purchase
from bot.models.rating import Rating

logger = logging.getLogger(__name__)


async def has_purchased(
    session: AsyncSession, user_id: int, book_id: int
) -> bool:
    """Check if user purchased any episode of a book."""
    r = await session.execute(
        select(Purchase.id)
        .where(
            Purchase.user_id == user_id,
            Purchase.book_id == book_id,
        )
        .limit(1)
    )
    return r.scalar_one_or_none() is not None


async def get_user_rating(
    session: AsyncSession, user_id: int, book_id: int
) -> Rating | None:
    """Get user's rating for a book (if any)."""
    r = await session.execute(
        select(Rating).where(
            Rating.user_id == user_id,
            Rating.book_id == book_id,
        )
    )
    return r.scalar_one_or_none()


async def upsert_rating(
    session: AsyncSession,
    user_id: int,
    book_id: int,
    stars: int,
    comment: str | None = None,
) -> Rating:
    """Create or update rating. Commits. Stars clamped to 1-5."""
    stars = max(1, min(5, int(stars)))
    if comment is not None:
        comment = comment.strip()[:500] or None

    existing = await get_user_rating(session, user_id, book_id)

    if existing is not None:
        existing.stars = stars
        if comment is not None:
            existing.comment = comment
        await session.commit()
        await session.refresh(existing)
        return existing

    r = Rating(
        user_id=user_id,
        book_id=book_id,
        stars=stars,
        comment=comment,
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)

    logger.info(f"Rating: u={user_id} b={book_id} {stars}*")
    return r


async def get_summary(
    session: AsyncSession, book_id: int
) -> tuple[float, int]:
    """Return (average_stars, count)."""
    r = await session.execute(
        select(
            func.avg(Rating.stars),
            func.count(Rating.id),
        ).where(Rating.book_id == book_id)
    )
    row = r.one()
    avg = float(row[0]) if row[0] is not None else 0.0
    cnt = int(row[1] or 0)
    return avg, cnt


async def list_recent(
    session: AsyncSession, book_id: int, limit: int = 5
) -> list[Rating]:
    """Recent reviews for a book."""
    r = await session.execute(
        select(Rating)
        .where(Rating.book_id == book_id)
        .order_by(Rating.updated_at.desc())
        .limit(limit)
    )
    return list(r.scalars().all())


async def delete_rating(
    session: AsyncSession, user_id: int, book_id: int
) -> bool:
    """Delete a user's rating."""
    r = await session.execute(
        delete(Rating).where(
            Rating.user_id == user_id,
            Rating.book_id == book_id,
        )
    )
    await session.commit()
    return (r.rowcount or 0) > 0
