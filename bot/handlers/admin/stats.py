"""Admin dashboard stats."""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards.admin_kb import stats_kb
from bot.services.admin_service import is_admin
from bot.services.db import SessionLocal
from bot.services.metrics_service import (
    dashboard_stats,
    top_books,
)
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_stats")


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


@router.callback_query(F.data == "stats:show")
async def show_stats(cb: CallbackQuery):
    if not await _ok(cb):
        return

    async with SessionLocal() as s:
        st = await dashboard_stats(s)

    text = (
        f"<b>DASHBOARD</b>\n\n"
        f"<b>Users</b>\n"
        f"Total: {st['total_users']:,}\n"
        f"Today: +{st['new_users_today']}\n\n"
        f"<b>Topup</b>\n"
        f"Today: {st['topups_today']} "
        f"({st['topup_amount_today']:,} Ks)\n"
        f"Pending: {st['pending_topups']}\n\n"
        f"<b>Sales</b>\n"
        f"Today: {st['purchases_today']} "
        f"({st['sales_amount_today']:,} Ks)\n\n"
        f"<b>Check-in</b>\n"
        f"Today: {st['checkins_today']}\n\n"
        f"Books: {st['total_books']}"
    )

    await edit_or_send(cb, text, reply_markup=stats_kb())
    await cb.answer()


@router.callback_query(F.data == "stats:top")
async def show_top(cb: CallbackQuery):
    if not await _ok(cb):
        return

    async with SessionLocal() as s:
        top = await top_books(s, days=7, limit=5)

    if not top:
        text = "<b>TOP BOOKS (7d)</b>\n\nမရှိသေးပါ။"
    else:
        lines = ["<b>TOP BOOKS (7d)</b>", ""]
        for i, (title, cnt) in enumerate(top, 1):
            lines.append(f"{i}. {title[:30]} — {cnt}")
        text = "\n".join(lines)

    await edit_or_send(cb, text, reply_markup=stats_kb())
    await cb.answer()
