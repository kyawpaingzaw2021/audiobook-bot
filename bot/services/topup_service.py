"""Topup service.

- create_topup: no commit (caller commits)
- mark_approved: no commit (atomic with wallet credit)
- mark_rejected / mark_cancelled: commit (terminal states)
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.topup import TopupRequest

logger = logging.getLogger(__name__)


async def is_duplicate_screenshot(
    session: AsyncSession, file_unique_id: str
) -> bool:
    """Check if screenshot was already used."""
    r = await session.execute(
        select(TopupRequest.id)
        .where(TopupRequest.file_unique_id == file_unique_id)
        .limit(1)
    )
    return r.scalar_one_or_none() is not None


async def create_topup(
    session: AsyncSession,
    user_id: int,
    amount: int,
    method: str,
    account_number: str,
    screenshot_file_id: str,
    file_unique_id: str,
) -> TopupRequest:
    """Create pending topup. Does NOT commit. Raises ValueError on dup."""
    t = TopupRequest(
        user_id=user_id,
        amount=amount,
        method=method,
        account_number=account_number,
        screenshot_file_id=screenshot_file_id,
        file_unique_id=file_unique_id,
        status="pending",
    )
    session.add(t)

    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise ValueError("Duplicate screenshot") from e

    logger.info(
        f"Topup created: #{t.id} u={user_id} {amount} {method}"
    )
    return t


async def get_topup(
    session: AsyncSession, topup_id: int
) -> TopupRequest | None:
    """Fetch topup by ID."""
    r = await session.execute(
        select(TopupRequest).where(TopupRequest.id == topup_id)
    )
    return r.scalar_one_or_none()


async def list_pending(
    session: AsyncSession, limit: int = 20
) -> list[TopupRequest]:
    """List pending topups (oldest first)."""
    r = await session.execute(
        select(TopupRequest)
        .where(TopupRequest.status == "pending")
        .order_by(TopupRequest.created_at.asc())
        .limit(limit)
    )
    return list(r.scalars().all())


async def count_pending(session: AsyncSession) -> int:
    """Count pending topups."""
    r = await session.execute(
        select(func.count(TopupRequest.id)).where(
            TopupRequest.status == "pending"
        )
    )
    return int(r.scalar() or 0)


async def mark_approved(
    session: AsyncSession,
    topup_id: int,
    admin_id: int,
    adjusted: int | None = None,
) -> TopupRequest | None:
    """Mark approved. Does NOT commit (caller commits)."""
    t = await get_topup(session, topup_id)
    if t is None or t.status != "pending":
        return None

    t.status = "approved"
    t.resolved_at = datetime.now(timezone.utc)
    t.resolved_by = admin_id
    if adjusted is not None:
        t.adjusted_amount = adjusted

    await session.flush()
    return t


async def mark_rejected(
    session: AsyncSession,
    topup_id: int,
    admin_id: int,
    reason: str,
) -> TopupRequest | None:
    """Mark rejected. Commits."""
    t = await get_topup(session, topup_id)
    if t is None or t.status != "pending":
        return None

    t.status = "rejected"
    t.reject_reason = reason
    t.resolved_at = datetime.now(timezone.utc)
    t.resolved_by = admin_id

    await session.commit()
    await session.refresh(t)
    return t


async def mark_cancelled(
    session: AsyncSession, topup_id: int, user_id: int
) -> bool:
    """Cancel pending topup. Commits. Ownership enforced."""
    t = await get_topup(session, topup_id)
    if t is None or t.status != "pending":
        return False
    if t.user_id != user_id:
        logger.warning(
            f"mark_cancelled: user {user_id} tried "
            f"#{topup_id} owned by {t.user_id}"
        )
        return False

    t.status = "cancelled"
    t.resolved_at = datetime.now(timezone.utc)
    await session.commit()
    return True


async def list_user_history(
    session: AsyncSession, user_id: int, limit: int = 10
) -> list[TopupRequest]:
    """Recent topups for a user."""
    r = await session.execute(
        select(TopupRequest)
        .where(TopupRequest.user_id == user_id)
        .order_by(TopupRequest.created_at.desc())
        .limit(limit)
    )
    return list(r.scalars().all())


async def expire_old(
    session: AsyncSession, hours: int = 24
) -> int:
    """Expire pending topups older than N hours. Commits."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    r = await session.execute(
        select(TopupRequest).where(
            TopupRequest.status == "pending",
            TopupRequest.created_at < cutoff,
        )
    )
    rows = list(r.scalars().all())

    if not rows:
        return 0

    for t in rows:
        t.status = "expired"
        t.resolved_at = datetime.now(timezone.utc)

    await session.commit()
    logger.info(f"Expired {len(rows)} topups (>{hours}h)")
    return len(rows)
