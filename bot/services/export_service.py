"""CSV export service. Uses asyncio.to_thread for file I/O."""
import asyncio
import csv
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.book import Book
from bot.models.ledger import Ledger
from bot.models.purchase import Purchase
from bot.models.user import User

logger = logging.getLogger(__name__)

EXPORT_DIR = Path("/opt/audiobook-bot/data/exports")
ENCODING = "utf-8-sig"


def _fmt_dt(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_csv(
    path: Path, headers: list[str], rows: list[tuple]
) -> None:
    """Synchronous writer — run in thread."""
    with open(path, "w", newline="", encoding=ENCODING) as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


async def export_users(session: AsyncSession) -> Path:
    """Export all users to CSV."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_DIR / f"users_{_ts()}.csv"

    r = await session.execute(select(User).order_by(User.id))
    users = list(r.scalars().all())

    headers = [
        "id", "tg_id", "username", "first_name",
        "balance", "accepted_terms", "is_blocked", "created_at",
    ]
    rows = [
        (
            u.id,
            u.tg_id,
            u.username or "",
            u.first_name or "",
            u.balance,
            u.accepted_terms,
            u.is_blocked,
            _fmt_dt(u.created_at),
        )
        for u in users
    ]

    await asyncio.to_thread(_write_csv, path, headers, rows)

    logger.info(f"Export users: {len(users)} -> {path.name}")
    return path


async def export_purchases(
    session: AsyncSession, days: int = 30
) -> Path:
    """Export recent purchases to CSV."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_DIR / f"purchases_{days}d_{_ts()}.csv"

    since = datetime.now(timezone.utc) - timedelta(days=days)

    r = await session.execute(
        select(Purchase)
        .where(Purchase.purchased_at >= since)
        .order_by(Purchase.id)
    )
    rows_db = list(r.scalars().all())

    book_ids = {p.book_id for p in rows_db}
    books: dict[int, str] = {}
    if book_ids:
        rb = await session.execute(
            select(Book.id, Book.title).where(
                Book.id.in_(book_ids)
            )
        )
        books = {bid: title for bid, title in rb.all()}

    headers = [
        "id", "user_id", "book_id", "book_title",
        "episode_no", "price_paid", "source", "purchased_at",
    ]
    rows = [
        (
            p.id,
            p.user_id,
            p.book_id,
            books.get(p.book_id, ""),
            p.episode_no,
            p.price_paid,
            p.source,
            _fmt_dt(p.purchased_at),
        )
        for p in rows_db
    ]

    await asyncio.to_thread(_write_csv, path, headers, rows)

    logger.info(
        f"Export purchases: {len(rows_db)} -> {path.name}"
    )
    return path


async def export_ledger(
    session: AsyncSession, days: int = 30
) -> Path:
    """Export recent ledger entries to CSV."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_DIR / f"ledger_{days}d_{_ts()}.csv"

    since = datetime.now(timezone.utc) - timedelta(days=days)

    r = await session.execute(
        select(Ledger)
        .where(Ledger.created_at >= since)
        .order_by(Ledger.id)
    )
    rows_db = list(r.scalars().all())

    headers = [
        "id", "user_id", "type", "amount",
        "balance_after", "note", "created_at",
    ]
    rows = [
        (
            r2.id,
            r2.user_id,
            r2.type,
            r2.amount,
            r2.balance_after,
            r2.note or "",
            _fmt_dt(r2.created_at),
        )
        for r2 in rows_db
    ]

    await asyncio.to_thread(_write_csv, path, headers, rows)

    logger.info(f"Export ledger: {len(rows_db)} -> {path.name}")
    return path


async def cleanup_old_exports(days: int = 3) -> int:
    """Delete export files older than N days."""
    try:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        cutoff = datetime.now().timestamp() - (days * 86400)
        count = 0
        for f in EXPORT_DIR.glob("*.csv"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                count += 1
        if count:
            logger.info(f"Cleaned {count} old exports")
        return count
    except Exception as e:
        logger.warning(f"Export cleanup failed: {e}")
        return 0
