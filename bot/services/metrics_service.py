"""Metrics service — dashboard stats (UTC-consistent)."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.book import Book
from bot.models.checkin import DailyCheckin
from bot.models.purchase import Purchase
from bot.models.topup import TopupRequest
from bot.models.user import User

logger = logging.getLogger(__name__)


def _utc_today_start() -> datetime:
    """UTC midnight today (timezone-aware)."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def dashboard_stats(session: AsyncSession) -> dict:
    """All-in-one dashboard metrics."""
    today = _utc_today_start()
    stats: dict = {}

    r = await session.execute(select(func.count(User.id)))
    stats["total_users"] = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(User.id)).where(
            User.created_at >= today
        )
    )
    stats["new_users_today"] = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(TopupRequest.id)).where(
            TopupRequest.status == "approved",
            TopupRequest.resolved_at >= today,
        )
    )
    stats["topups_today"] = int(r.scalar() or 0)

    r = await session.execute(
        select(func.coalesce(func.sum(TopupRequest.amount), 0))
        .where(
            TopupRequest.status == "approved",
            TopupRequest.resolved_at >= today,
        )
    )
    stats["topup_amount_today"] = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(TopupRequest.id))
        .where(TopupRequest.status == "pending")
    )
    stats["pending_topups"] = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(Purchase.id))
        .where(Purchase.purchased_at >= today)
    )
    stats["purchases_today"] = int(r.scalar() or 0)

    r = await session.execute(
        select(func.coalesce(func.sum(Purchase.price_paid), 0))
        .where(Purchase.purchased_at >= today)
    )
    stats["sales_amount_today"] = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(DailyCheckin.id))
        .where(DailyCheckin.created_at >= today)
    )
    stats["checkins_today"] = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(Book.id))
        .where(Book.is_active == True)  # noqa: E712
    )
    stats["total_books"] = int(r.scalar() or 0)

    return stats


async def top_books(
    session: AsyncSession, days: int = 7, limit: int = 5
) -> list[tuple[str, int]]:
    """Top books by purchase count (single JOIN)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    r = await session.execute(
        select(
            Book.title,
            func.count(Purchase.id).label("cnt"),
        )
        .join(Book, Book.id == Purchase.book_id)
        .where(Purchase.purchased_at >= since)
        .group_by(Book.id, Book.title)
        .order_by(func.count(Purchase.id).desc())
        .limit(limit)
    )
    return [(title, int(cnt)) for title, cnt in r.all()]
