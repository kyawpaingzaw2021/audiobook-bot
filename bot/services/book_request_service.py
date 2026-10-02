"""Book request service."""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.book_request import BookRequest

logger = logging.getLogger(__name__)


async def find_pending_similar(
    session: AsyncSession, title: str, user_id: int
) -> BookRequest | None:
    """Find existing pending request with same title."""
    r = await session.execute(
        select(BookRequest).where(
            BookRequest.user_id == user_id,
            BookRequest.status == "pending",
            func.lower(BookRequest.title) == title.lower().strip(),
        )
    )
    return r.scalar_one_or_none()


async def create(
    session: AsyncSession,
    user_id: int,
    title: str,
    author: str | None = None,
    note: str | None = None,
) -> BookRequest:
    """Create a book request. Idempotent + race-safe."""
    title = title.strip()[:255]
    existing = await find_pending_similar(session, title, user_id)
    if existing is not None:
        return existing

    r = BookRequest(
        user_id=user_id,
        title=title,
        author=(author.strip()[:255] if author else None),
        note=(note.strip()[:500] if note else None),
    )
    session.add(r)

    try:
        await session.commit()
        await session.refresh(r)
        logger.info(f"Book request #{r.id}: '{title}' by u={user_id}")
        return r
    except IntegrityError:
        await session.rollback()
        existing = await find_pending_similar(
            session, title, user_id
        )
        if existing is not None:
            return existing
        raise


async def list_pending(
    session: AsyncSession, limit: int = 30
) -> list[BookRequest]:
    """List pending requests (oldest first)."""
    r = await session.execute(
        select(BookRequest)
        .where(BookRequest.status == "pending")
        .order_by(BookRequest.created_at.asc())
        .limit(limit)
    )
    return list(r.scalars().all())


async def list_user(
    session: AsyncSession, user_id: int, limit: int = 10
) -> list[BookRequest]:
    """Recent requests from a user."""
    r = await session.execute(
        select(BookRequest)
        .where(BookRequest.user_id == user_id)
        .order_by(BookRequest.created_at.desc())
        .limit(limit)
    )
    return list(r.scalars().all())


async def count_pending(session: AsyncSession) -> int:
    """Count pending requests."""
    r = await session.execute(
        select(func.count(BookRequest.id)).where(
            BookRequest.status == "pending"
        )
    )
    return int(r.scalar() or 0)


async def get(
    session: AsyncSession, req_id: int
) -> BookRequest | None:
    """Fetch request by ID."""
    r = await session.execute(
        select(BookRequest).where(BookRequest.id == req_id)
    )
    return r.scalar_one_or_none()


async def mark_added(
    session: AsyncSession,
    req_id: int,
    admin_id: int,
    book_id: int,
) -> BookRequest | None:
    """Mark as added. Commits."""
    r = await get(session, req_id)
    if r is None:
        return None

    r.status = "added"
    r.book_id = book_id
    r.resolved_at = datetime.now(timezone.utc)
    r.resolved_by = admin_id

    await session.commit()
    await session.refresh(r)
    return r


async def mark_rejected(
    session: AsyncSession,
    req_id: int,
    admin_id: int,
    note: str,
) -> BookRequest | None:
    """Mark as rejected. Commits."""
    r = await get(session, req_id)
    if r is None:
        return None

    r.status = "rejected"
    r.admin_note = note
    r.resolved_at = datetime.now(timezone.utc)
    r.resolved_by = admin_id

    await session.commit()
    await session.refresh(r)
    return r
