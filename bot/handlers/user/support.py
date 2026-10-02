"""Support contact handler."""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.services.db import SessionLocal
from bot.services.settings_service import get_setting

logger = logging.getLogger(__name__)
router = Router(name="user_support")


@router.message(F.text == "☎️ Support")
async def show_support(message: Message):
    async with SessionLocal() as s:
        tg = await get_setting(s, "support_telegram")
        ph = await get_setting(s, "support_phone")
        hrs = await get_setting(s, "support_hours")
        email = await get_setting(s, "support_email")

    text = "<b>SUPPORT</b>\n\n"
    if tg:
        text += f"Telegram: {tg}\n"
    if ph:
        text += f"Phone: {ph}\n"
    if email:
        text += f"Email: {email}\n"
    if hrs:
        text += f"Hours: {hrs}\n"

    text += (
        "\n<b>မှတ်ချက်</b>\n"
        "Topup ပြဿနာရှိရင် screenshot + user ID ပို့ပါ။\n\n"
        "<b>သတိပြုပါ</b>\n"
        "Bot က admin အမည်နဲ့ DM ဘယ်တော့မှ မလုပ်ပါ။"
    )

    await message.answer(text)


@router.callback_query(F.data == "support:show")
async def support_cb(cb: CallbackQuery):
    await cb.message.answer(
        "Support အတွက် [☎️ Support] button ကို နှိပ်ပါ။"
    )
    await cb.answer()
