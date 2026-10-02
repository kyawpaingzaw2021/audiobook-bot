"""Daily check-in handler."""
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.keyboards.user_kb import daily_kb
from bot.services.checkin_service import (
    MM_TZ,
    do_checkin,
    get_last_checkin,
    has_checked_in_today,
    today_mm,
    tomorrow_mm_reset,
)
from bot.services.db import SessionLocal
from bot.services.purchase_service import get_user_by_tg
from bot.services.settings_service import get_int_setting

logger = logging.getLogger(__name__)
router = Router(name="user_daily")


def _hours_left() -> str:
    """Time remaining until next midnight (MM time)."""
    now_mm = datetime.now(MM_TZ)
    reset = tomorrow_mm_reset()
    diff = reset - now_mm
    total_min = max(0, int(diff.total_seconds() // 60))
    h, m = divmod(total_min, 60)
    return f"{h}h {m}m"


@router.message(F.text == "🎁 Daily")
async def show_daily(message: Message):
    async with SessionLocal() as s:
        user = await get_user_by_tg(s, message.from_user.id)
        if user is None:
            await message.answer("/start အရင် ပို့ပါ")
            return

        reward = await get_int_setting(s, "daily_reward", 5)
        checked = await has_checked_in_today(s, user.id)
        last = await get_last_checkin(s, user.id)

    streak = last.streak_count if last else 0

    if checked:
        text = (
            "<b>Check-in ပြီးသား</b>\n\n"
            f"ဒီနေ့ စစ်ပြီး — {reward:,} Ks ရပြီ\n"
            f"Streak: {streak} days\n\n"
            f"နောက်စစ်ရန်: {_hours_left()} ကျန်"
        )
        can = False
    else:
        text = (
            "<b>DAILY CHECK-IN</b>\n\n"
            f"ဒီနေ့: {today_mm().strftime('%d %b %Y')}\n\n"
            f"Reward: {reward:,} Ks\n"
            f"Streak: {streak} days\n\n"
        )
        if streak > 0:
            text += "7 days ဆက် — +20 Ks bonus\n"
        can = True

    await message.answer(text, reply_markup=daily_kb(can))


@router.callback_query(F.data == "daily:do")
async def do_daily(cb: CallbackQuery):
    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        if user is None:
            await cb.answer("/start ပို့ပါ", show_alert=True)
            return

        reward = await get_int_setting(s, "daily_reward", 5)

        ok, msg, new_bal, streak, total = await do_checkin(
            s, cb.from_user.id, base_reward=reward
        )

        if ok:
            await s.commit()

    if not ok:
        await cb.answer(msg, show_alert=True)
        return

    text = (
        "<b>Check-in ပြီး</b>\n\n"
        f"+{total:,} Ks\n"
    )
    if msg.startswith("streak_bonus:"):
        bonus = int(msg.split(":")[1])
        text += f"Streak Bonus: +{bonus:,} Ks\n"

    text += (
        f"\nStreak: {streak} days\n"
        f"Balance: {new_bal:,} Ks"
    )

    try:
        await cb.message.edit_text(
            text, reply_markup=daily_kb(False)
        )
    except Exception:
        await cb.message.answer(
            text, reply_markup=daily_kb(False)
        )

    await cb.answer(f"+{total:,} Ks")


@router.callback_query(F.data == "daily:back")
async def daily_back(cb: CallbackQuery):
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer()
