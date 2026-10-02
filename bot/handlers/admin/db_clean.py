"""Admin — DB cleanup (manual preview + delete)."""
import logging
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import delete, func, select

from bot.keyboards.admin_kb import (
    clean_confirm_kb,
    clean_final_kb,
    db_clean_kb,
)
from bot.services.admin_service import is_admin
from bot.services.db import SessionLocal
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_clean")


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


@router.callback_query(F.data == "set:clean")
async def clean_menu(cb: CallbackQuery):
    if not await _ok(cb):
        return

    await edit_or_send(
        cb,
        "<b>DATABASE CLEANUP</b>\n\n"
        "ဖျက်တာ ပြန်မရပါ။\n\n"
        "Preview ကြည့်ပြီးမှ ဆက်ပါ။",
        reply_markup=db_clean_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "clean:stats")
async def clean_stats(cb: CallbackQuery):
    if not await _ok(cb):
        return

    from bot.models import (
        Admin,
        Book,
        BookFile,
        BookRequest,
        Category,
        DailyCheckin,
        Ledger,
        PromoCode,
        PromoRedemption,
        Purchase,
        Rating,
        Referral,
        Setting,
        TopupRequest,
        User,
        UserCode,
        Wishlist,
    )

    tables = [
        ("Users", User),
        ("Categories", Category),
        ("Books", Book),
        ("Book Files", BookFile),
        ("Admins", Admin),
        ("Purchases", Purchase),
        ("Ledger", Ledger),
        ("Topups", TopupRequest),
        ("Checkins", DailyCheckin),
        ("Referrals", Referral),
        ("User Codes", UserCode),
        ("Promos", PromoCode),
        ("Redemptions", PromoRedemption),
        ("Wishlists", Wishlist),
        ("Ratings", Rating),
        ("Book Requests", BookRequest),
        ("Settings", Setting),
    ]

    lines = ["<b>DATABASE STATS</b>", ""]
    total = 0

    async with SessionLocal() as s:
        for name, model in tables:
            r = await s.execute(
                select(func.count()).select_from(model)
            )
            cnt = int(r.scalar() or 0)
            total += cnt
            lines.append(f"{name:.<20} {cnt:>6,}")

    lines.append("")
    lines.append(f"{'TOTAL':.<20} {total:>6,}")

    await edit_or_send(
        cb, "\n".join(lines), reply_markup=db_clean_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "clean:audit")
async def clean_audit(cb: CallbackQuery):
    if not await _ok(cb):
        return

    from bot.models.ledger import Ledger

    cutoff = datetime.now(timezone.utc) - timedelta(days=180)

    async with SessionLocal() as s:
        r = await s.execute(
            select(func.count(Ledger.id)).where(
                Ledger.created_at < cutoff
            )
        )
        cnt = int(r.scalar() or 0)

        r2 = await s.execute(
            select(Ledger)
            .where(Ledger.created_at < cutoff)
            .order_by(Ledger.id.desc())
            .limit(5)
        )
        samples = list(r2.scalars().all())

        r3 = await s.execute(select(func.count(Ledger.id)))
        total = int(r3.scalar() or 0)

    text = (
        f"<b>CLEAN LEDGER (180d+)</b>\n\n"
        f"Delete: {cnt:,}\n"
        f"Remaining: {total - cnt:,}\n\n"
        f"Sample:\n"
    )
    for row in samples:
        d = (
            row.created_at.strftime("%Y-%m-%d")
            if row.created_at else "?"
        )
        text += f"  #{row.id} | {row.type} | {row.amount:+d} | {d}\n"

    await edit_or_send(
        cb,
        text,
        reply_markup=clean_confirm_kb("ledger", "180"),
    )
    await cb.answer()


@router.callback_query(F.data == "clean:topup")
async def clean_topup(cb: CallbackQuery):
    if not await _ok(cb):
        return

    from bot.models.topup import TopupRequest

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    terminal = ["approved", "rejected", "cancelled", "expired"]

    async with SessionLocal() as s:
        r = await s.execute(
            select(func.count(TopupRequest.id)).where(
                TopupRequest.status.in_(terminal),
                TopupRequest.created_at < cutoff,
            )
        )
        cnt = int(r.scalar() or 0)

        r2 = await s.execute(
            select(TopupRequest)
            .where(
                TopupRequest.status.in_(terminal),
                TopupRequest.created_at < cutoff,
            )
            .limit(5)
        )
        samples = list(r2.scalars().all())

    text = (
        f"<b>CLEAN RESOLVED TOPUPS (30d+)</b>\n\n"
        f"Delete: {cnt:,}\n\n"
        f"Sample:\n"
    )
    for t in samples:
        d = (
            t.created_at.strftime("%Y-%m-%d")
            if t.created_at else "?"
        )
        text += f"  #{t.id} | {t.amount:,} | {t.status} | {d}\n"

    await edit_or_send(
        cb,
        text,
        reply_markup=clean_confirm_kb("topup", "30"),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("clean:do:"))
async def clean_confirm(cb: CallbackQuery):
    if not await _ok(cb):
        return

    parts = cb.data.split(":")
    if len(parts) != 4:
        await cb.answer("Invalid", show_alert=True)
        return

    action, target = parts[2], parts[3]

    await edit_or_send(
        cb,
        f"<b>အတည်ပြုပါ (1/2)</b>\n\n"
        f"Action: <b>{action}</b>\n"
        f"Target: <b>{target}d+</b>\n\n"
        f"ဒါက ပြန်မရနိုင်ပါ။",
        reply_markup=clean_final_kb(action, target),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("clean:final:"))
async def clean_final(cb: CallbackQuery):
    if not await _ok(cb):
        return

    parts = cb.data.split(":")
    if len(parts) != 4:
        await cb.answer("Invalid", show_alert=True)
        return

    action, target = parts[2], parts[3]

    try:
        days = int(target)
    except ValueError:
        await cb.answer("Invalid", show_alert=True)
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    await edit_or_send(cb, "Deleting...")

    deleted = 0

    if action == "ledger":
        from bot.models.ledger import Ledger

        async with SessionLocal() as s:
            r = await s.execute(
                delete(Ledger).where(Ledger.created_at < cutoff)
            )
            await s.commit()
            deleted = r.rowcount or 0

    elif action == "topup":
        from bot.models.topup import TopupRequest

        terminal = [
            "approved", "rejected", "cancelled", "expired"
        ]

        async with SessionLocal() as s:
            r = await s.execute(
                delete(TopupRequest).where(
                    TopupRequest.status.in_(terminal),
                    TopupRequest.created_at < cutoff,
                )
            )
            await s.commit()
            deleted = r.rowcount or 0

    logger.info(
        f"DB Clean: {action} ({target}d) -> {deleted} rows "
        f"by {cb.from_user.id}"
    )

    now_str = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M"
    )

    await edit_or_send(
        cb,
        f"<b>DELETED</b>\n\n"
        f"Table: {action}\n"
        f"Cutoff: {target}d+\n"
        f"Deleted: <b>{deleted:,}</b> rows\n"
        f"{now_str} UTC",
        reply_markup=db_clean_kb(),
    )
    await cb.answer("Deleted")
