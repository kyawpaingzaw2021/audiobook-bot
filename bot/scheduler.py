"""APScheduler — backup, expire, report, reengage."""
import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import config

logger = logging.getLogger(__name__)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Register all scheduled jobs (UTC)."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        _daily_backup,
        trigger=CronTrigger(hour=3, minute=0),
        args=[bot],
        id="daily_backup",
        replace_existing=True,
    )

    scheduler.add_job(
        _expire_topups,
        trigger=CronTrigger(minute=0),
        id="expire_topups",
        replace_existing=True,
    )

    scheduler.add_job(
        _daily_report,
        trigger=CronTrigger(hour=2, minute=30),
        args=[bot],
        id="daily_report",
        replace_existing=True,
    )

    scheduler.add_job(
        _reengage,
        trigger=CronTrigger(hour=12, minute=0),
        args=[bot],
        id="reengage",
        replace_existing=True,
    )

    logger.info(
        "Scheduler: backup 03:00, expire hourly, "
        "report 02:30, reengage 12:00"
    )
    return scheduler


async def _daily_backup(bot: Bot):
    logger.info("Running daily backup...")

    from bot.services.backup_service import run_backup

    ok, msg = await run_backup(bot)

    if ok:
        logger.info(f"Backup OK: {msg}")
        return

    logger.error(f"Backup FAILED: {msg}")

    if config.ADMIN_ID == 0:
        return

    try:
        await bot.send_message(
            chat_id=config.ADMIN_ID,
            text=f"<b>Backup FAILED</b>\n\n{msg}",
        )
    except Exception as e:
        logger.error(f"Admin notify failed: {e}")


async def _expire_topups():
    logger.info("Expiring old topups...")

    from bot.services.db import SessionLocal
    from bot.services.settings_service import (
        get_topup_expire_hours,
    )
    from bot.services.topup_service import expire_old

    try:
        async with SessionLocal() as session:
            hours = await get_topup_expire_hours(session)
            count = await expire_old(session, hours=hours)

        if count:
            logger.info(f"Expired {count} topups (>{hours}h)")
    except Exception as e:
        logger.exception(f"Expire failed: {e}")


async def _daily_report(bot: Bot):
    logger.info("Daily report...")

    if config.ADMIN_ID == 0:
        return

    from aiogram.types import (
        InlineKeyboardButton,
        InlineKeyboardMarkup,
    )

    from bot.services.db import SessionLocal
    from bot.services.metrics_service import (
        dashboard_stats,
        top_books,
    )

    try:
        async with SessionLocal() as session:
            st = await dashboard_stats(session)
            top = await top_books(session, days=1, limit=3)

        text = (
            f"<b>DAILY REPORT</b>\n\n"
            f"New users: +{st['new_users_today']}\n"
            f"Topups: {st['topups_today']} "
            f"({st['topup_amount_today']:,} Ks)\n"
            f"Sales: {st['purchases_today']} "
            f"({st['sales_amount_today']:,} Ks)\n"
            f"Checkins: {st['checkins_today']}\n"
            f"Pending: {st['pending_topups']}\n"
        )

        if top:
            text += "\nTop today:\n"
            for i, (title, cnt) in enumerate(top, 1):
                text += f"  {i}. {title[:25]} — {cnt}\n"

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Panel",
                    callback_data="admin:panel",
                )]
            ]
        )

        await bot.send_message(
            chat_id=config.ADMIN_ID,
            text=text,
            reply_markup=kb,
        )
    except Exception as e:
        logger.exception(f"Daily report: {e}")


async def _reengage(bot: Bot):
    logger.info("Re-engagement...")

    from datetime import timedelta

    from sqlalchemy import select, update

    from bot.models.book import Book
    from bot.models.user import User
    from bot.services.db import SessionLocal
    from bot.services.settings_service import get_int_setting

    try:
        async with SessionLocal() as s:
            days = await get_int_setting(
                s, "reengage_days", 7
            )

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        async with SessionLocal() as s:
            r = await s.execute(
                select(User.tg_id, User.first_name)
                .where(
                    User.is_blocked == False,  # noqa: E712
                    User.updated_at < cutoff,
                )
                .limit(50)
            )
            users = [
                {"tg_id": row[0], "name": row[1]}
                for row in r.all()
            ]

            r = await s.execute(
                select(
                    Book.title,
                    Book.episode_price,
                    Book.id,
                )
                .where(Book.is_active == True)  # noqa: E712
                .order_by(Book.created_at.desc())
                .limit(3)
            )
            books = [
                {
                    "title": row[0],
                    "price": row[1],
                    "id": row[2],
                }
                for row in r.all()
            ]

        if not books or not users:
            return

        blocked_tg_ids: list[int] = []

        for u in users:
            try:
                safe_name = (
                    (u["name"] or "User")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )

                text = (
                    f"<b>မင်္ဂလာပါ {safe_name}</b>\n\n"
                    f"Audiobook အသစ်များ ရောက်ပါပြီ!\n\n"
                )
                for b in books:
                    safe_title = (
                        b["title"]
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )
                    text += (
                        f"{safe_title}\n"
                        f"  {b['price']:,} Ks/episode\n\n"
                    )

                await bot.send_message(
                    chat_id=u["tg_id"],
                    text=text,
                )
                await asyncio.sleep(0.5)
            except Exception as e:
                err = str(e).lower()
                if (
                    "blocked" in err
                    or "chat not found" in err
                    or "deactivated" in err
                ):
                    blocked_tg_ids.append(u["tg_id"])
                logger.debug(
                    f"Reengage skip {u['tg_id']}: {e}"
                )

        if blocked_tg_ids:
            try:
                async with SessionLocal() as s:
                    await s.execute(
                        update(User)
                        .where(User.tg_id.in_(blocked_tg_ids))
                        .values(is_blocked=True)
                    )
                    await s.commit()
                logger.info(
                    f"Marked {len(blocked_tg_ids)} users blocked"
                )
            except Exception as e:
                logger.warning(f"Mark blocked: {e}")

        sent = len(users) - len(blocked_tg_ids)
        logger.info(f"Reengaged {sent}/{len(users)} users")
    except Exception as e:
        logger.exception(f"Reengage: {e}")
