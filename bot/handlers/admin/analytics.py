"""Admin analytics — revenue, growth, funnel, top lists."""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards.admin_kb import analytics_kb
from bot.services.admin_service import is_admin
from bot.services.analytics_service import (
    funnel,
    overall_kpis,
    revenue_series,
    top_books,
    top_categories,
    user_growth,
)
from bot.services.db import SessionLocal
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_analytics")


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


def _bar(value: int, max_value: int, width: int = 10) -> str:
    if max_value <= 0:
        return "░" * width
    n = min(width, int(round(value / max_value * width)))
    if n < 0:
        n = 0
    return "█" * n + "░" * (width - n)


@router.callback_query(F.data == "ana:menu")
async def ana_menu(cb: CallbackQuery):
    if not await _ok(cb):
        return

    async with SessionLocal() as s:
        k = await overall_kpis(s)

    text = (
        f"<b>ANALYTICS</b>\n\n"
        f"Users: {k['total_users']:,}\n"
        f"Active 7d: {k['active_7d']:,}\n\n"
        f"Topup 30d: {k['topup_30d']:,} Ks\n"
        f"Sales 30d: {k['sales_30d']:,} Ks\n\n"
        f"Pending topups: {k['pending_topups']}\n"
        f"Pending requests: {k['pending_reqs']}\n"
        f"Active books: {k['total_books']}\n"
        f"Checkins today: {k['checkins_today']}"
    )

    await edit_or_send(cb, text, reply_markup=analytics_kb())
    await cb.answer()


@router.callback_query(F.data.in_({"ana:rev7", "ana:rev30"}))
async def ana_rev(cb: CallbackQuery):
    if not await _ok(cb):
        return

    days = 7 if cb.data == "ana:rev7" else 30

    async with SessionLocal() as s:
        series = await revenue_series(s, days=days)

    max_val = max(
        (max(t, p) for _, t, p in series), default=0
    )

    lines = [f"<b>REVENUE ({days}d)</b>", ""]
    total_t = 0
    total_p = 0

    for label, topup, sales in series:
        total_t += topup
        total_p += sales
        bar = _bar(max(topup, sales), max_val)
        lines.append(f"{label} {bar}")
        lines.append(f"  Topup {topup:,} | Sales {sales:,}")

    lines += [
        "",
        f"Total Topup: {total_t:,} Ks",
        f"Total Sales: {total_p:,} Ks",
    ]

    await edit_or_send(
        cb, "\n".join(lines), reply_markup=analytics_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "ana:growth")
async def ana_growth(cb: CallbackQuery):
    if not await _ok(cb):
        return

    async with SessionLocal() as s:
        series = await user_growth(s, days=14)

    max_val = max((v for _, v in series), default=0)
    total = sum(v for _, v in series)

    lines = ["<b>USER GROWTH (14d)</b>", ""]
    for label, v in series:
        bar = _bar(v, max_val)
        lines.append(f"{label} {bar} {v}")

    lines += ["", f"New: {total}"]

    await edit_or_send(
        cb, "\n".join(lines), reply_markup=analytics_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "ana:funnel")
async def ana_funnel(cb: CallbackQuery):
    if not await _ok(cb):
        return

    async with SessionLocal() as s:
        new_users, topup_users, purchase_users = await funnel(
            s, days=30
        )

    def pct(n: int, d: int) -> int:
        if d <= 0:
            return 0
        return int(round(n / d * 100))

    text = (
        f"<b>FUNNEL (30d)</b>\n\n"
        f"New users:      {new_users:,}\n"
        f"  -> {pct(topup_users, new_users)}%\n"
        f"Topped up:      {topup_users:,}\n"
        f"  -> {pct(purchase_users, topup_users)}%\n"
        f"Purchased:      {purchase_users:,}\n\n"
        f"Conversion: {pct(purchase_users, new_users)}%"
    )

    await edit_or_send(cb, text, reply_markup=analytics_kb())
    await cb.answer()


@router.callback_query(F.data == "ana:books")
async def ana_books(cb: CallbackQuery):
    if not await _ok(cb):
        return

    async with SessionLocal() as s:
        top = await top_books(s, days=30, limit=5)

    lines = ["<b>TOP BOOKS (30d)</b>", ""]
    if not top:
        lines.append("မရှိသေးပါ။")
    else:
        for i, (title, cnt, rev) in enumerate(top, 1):
            lines.append(f"{i}. {title[:28]}")
            lines.append(f"   {cnt} sales | {rev:,} Ks")
            lines.append("")

    await edit_or_send(
        cb, "\n".join(lines), reply_markup=analytics_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "ana:cats")
async def ana_cats(cb: CallbackQuery):
    if not await _ok(cb):
        return

    async with SessionLocal() as s:
        top = await top_categories(s, days=30, limit=5)

    lines = ["<b>TOP CATEGORIES (30d)</b>", ""]
    if not top:
        lines.append("မရှိသေးပါ။")
    else:
        for i, (name, cnt) in enumerate(top, 1):
            lines.append(f"{i}. {name} — {cnt}")

    await edit_or_send(
        cb, "\n".join(lines), reply_markup=analytics_kb()
    )
    await cb.answer()
