"""Analytics service — revenue, growth, funnel, top lists."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.book import Book
from bot.models.book_request import BookRequest
from bot.models.category import Category
from bot.models.checkin import DailyCheckin
from bot.models.purchase import Purchase
from bot.models.topup import TopupRequest
from bot.models.user import User

logger = logging.getLogger(__name__)


def _utc_day(d: datetime) -> datetime:
    """Zero out time components."""
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


async def revenue_series(
    session: AsyncSession, days: int = 7
) -> list[tuple[str, int, int]]:
    """Daily (label, topup_total, sales_total) for last N days."""
    since = _utc_day(
        datetime.now(timezone.utc) - timedelta(days=days - 1)
    )

    r = await session.execute(
        select(
            func.date_trunc(
                "day", TopupRequest.resolved_at
            ).label("d"),
            func.coalesce(func.sum(TopupRequest.amount), 0),
        )
        .where(
            TopupRequest.status == "approved",
            TopupRequest.resolved_at >= since,
        )
        .group_by("d")
    )
    topup_map = {row[0].date(): int(row[1]) for row in r.all()}

    r = await session.execute(
        select(
            func.date_trunc(
                "day", Purchase.purchased_at
            ).label("d"),
            func.coalesce(func.sum(Purchase.price_paid), 0),
        )
        .where(Purchase.purchased_at >= since)
        .group_by("d")
    )
    sales_map = {row[0].date(): int(row[1]) for row in r.all()}

    out: list[tuple[str, int, int]] = []
    today = datetime.now(timezone.utc).date()
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        label = d.strftime("%d %b")
        out.append(
            (label, topup_map.get(d, 0), sales_map.get(d, 0))
        )
    return out


async def user_growth(
    session: AsyncSession, days: int = 14
) -> list[tuple[str, int]]:
    """Daily new user count for last N days."""
    since = _utc_day(
        datetime.now(timezone.utc) - timedelta(days=days - 1)
    )

    r = await session.execute(
        select(
            func.date_trunc("day", User.created_at).label("d"),
            func.count(User.id),
        )
        .where(User.created_at >= since)
        .group_by("d")
    )
    day_map = {row[0].date(): int(row[1]) for row in r.all()}

    out: list[tuple[str, int]] = []
    today = datetime.now(timezone.utc).date()
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        out.append((d.strftime("%d %b"), day_map.get(d, 0)))
    return out


async def funnel(
    session: AsyncSession, days: int = 30
) -> tuple[int, int, int]:
    """(new_users, topup_users, purchase_users) for last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    r = await session.execute(
        select(func.count(User.id))
        .where(User.created_at >= since)
    )
    new_users = int(r.scalar() or 0)

    r = await session.execute(
        select(
            func.count(func.distinct(TopupRequest.user_id))
        )
        .where(
            TopupRequest.status == "approved",
            TopupRequest.resolved_at >= since,
        )
    )
    topup_users = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(func.distinct(Purchase.user_id)))
        .where(Purchase.purchased_at >= since)
    )
    purchase_users = int(r.scalar() or 0)

    return new_users, topup_users, purchase_users


async def top_books(
    session: AsyncSession, days: int = 30, limit: int = 5
) -> list[tuple[str, int, int]]:
    """Top books by count + revenue (single JOIN)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    r = await session.execute(
        select(
            Book.title,
            func.count(Purchase.id).label("cnt"),
            func.coalesce(
                func.sum(Purchase.price_paid), 0
            ).label("rev"),
        )
        .join(Book, Book.id == Purchase.book_id)
        .where(Purchase.purchased_at >= since)
        .group_by(Book.id, Book.title)
        .order_by(func.count(Purchase.id).desc())
        .limit(limit)
    )
    return [
        (title, int(cnt), int(rev))
        for title, cnt, rev in r.all()
    ]


async def top_categories(
    session: AsyncSession, days: int = 30, limit: int = 5
) -> list[tuple[str, int]]:
    """Top categories by purchase count (single JOIN)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    r = await session.execute(
        select(
            Category.name,
            func.count(Purchase.id).label("cnt"),
        )
        .select_from(Purchase)
        .join(Book, Book.id == Purchase.book_id)
        .outerjoin(Category, Category.id == Book.category_id)
        .where(Purchase.purchased_at >= since)
        .group_by(Category.name)
        .order_by(func.count(Purchase.id).desc())
        .limit(limit)
    )
    return [(name or "—", int(cnt)) for name, cnt in r.all()]


async def overall_kpis(session: AsyncSession) -> dict:
    """High-level KPIs for analytics menu."""
    now = datetime.now(timezone.utc)
    today = _utc_day(now)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    r = await session.execute(select(func.count(User.id)))
    total_users = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(func.distinct(Purchase.user_id)))
        .where(Purchase.purchased_at >= d7)
    )
    active_7d = int(r.scalar() or 0)

    r = await session.execute(
        select(func.coalesce(func.sum(Purchase.price_paid), 0))
        .where(Purchase.purchased_at >= d30)
    )
    sales_30d = int(r.scalar() or 0)

    r = await session.execute(
        select(func.coalesce(func.sum(TopupRequest.amount), 0))
        .where(
            TopupRequest.status == "approved",
            TopupRequest.resolved_at >= d30,
        )
    )
    topup_30d = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(TopupRequest.id))
        .where(TopupRequest.status == "pending")
    )
    pending_topups = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(BookRequest.id))
        .where(BookRequest.status == "pending")
    )
    pending_reqs = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(Book.id))
        .where(Book.is_active == True)  # noqa: E712
    )
    total_books = int(r.scalar() or 0)

    r = await session.execute(
        select(func.count(DailyCheckin.id))
        .where(DailyCheckin.created_at >= today)
    )
    checkins_today = int(r.scalar() or 0)

    return {
        "total_users": total_users,
        "active_7d": active_7d,
        "sales_30d": sales_30d,
        "topup_30d": topup_30d,
        "pending_topups": pending_topups,
        "pending_reqs": pending_reqs,
        "total_books": total_books,
        "checkins_today": checkins_today,
    }
