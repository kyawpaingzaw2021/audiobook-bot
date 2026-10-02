"""Referral info + share link."""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.keyboards.user_kb import referral_kb
from bot.services.db import SessionLocal
from bot.services.purchase_service import get_user_by_tg
from bot.services.referral_service import (
    count_paid,
    count_referrals,
    get_or_create_code,
)
from bot.services.settings_service import get_int_setting

logger = logging.getLogger(__name__)
router = Router(name="user_referral")


@router.message(F.text == "👥 Referral")
async def show_referral(message: Message):
    async with SessionLocal() as s:
        user = await get_user_by_tg(s, message.from_user.id)
        if user is None:
            await message.answer("/start အရင် ပို့ပါ")
            return

        code = await get_or_create_code(
            s, user.id, user.tg_id
        )
        total = await count_referrals(s, user.id)
        paid = await count_paid(s, user.id)
        bonus = await get_int_setting(
            s, "referral_bonus", 200
        )

    try:
        me = await message.bot.get_me()
        bot_username = me.username or "yourbot"
    except Exception:
        bot_username = "yourbot"

    link = f"https://t.me/{bot_username}?start=ref_{code}"

    text = (
        "<b>REFERRAL</b>\n\n"
        f"Your Code:\n<code>{code}</code>\n\n"
        f"Link:\n<code>{link}</code>\n\n"
        f"Bonus: {bonus:,} Ks\n"
        "(friend ပထမဆုံး ဝယ်တဲ့အခါ)\n\n"
        f"Invited: {total}\n"
        f"Paid: {paid}"
    )

    await message.answer(text, reply_markup=referral_kb(link))


@router.callback_query(F.data == "ref:back")
async def ref_back(cb: CallbackQuery):
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer()
