"""Promo code list + apply."""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.keyboards.user_kb import promo_list_kb
from bot.services.db import SessionLocal
from bot.services.promo_service import list_active

logger = logging.getLogger(__name__)
router = Router(name="user_promo")


@router.message(F.text == "🎟️ Promo")
async def show_promo(message: Message):
    async with SessionLocal() as s:
        codes = await list_active(s)

    if not codes:
        await message.answer(
            "<b>PROMO CODES</b>\n\n"
            "လက်ရှိ code မရှိပါ။"
        )
        return

    text = (
        f"<b>PROMO CODES ({len(codes)})</b>\n\n"
        "ရွေးပြီး သုံးလို့ရပါတယ်။\n"
        "ဝယ်တဲ့အခါ code ကို ထည့်ပါ။"
    )

    await message.answer(text, reply_markup=promo_list_kb(codes))


@router.callback_query(F.data.startswith("promo:use:"))
async def use_promo(cb: CallbackQuery):
    parts = cb.data.split(":", 2)
    if len(parts) < 3:
        await cb.answer("Invalid", show_alert=True)
        return

    code = parts[2]

    await cb.message.answer(
        f"Code: <code>{code}</code>\n\n"
        "ဝယ်တဲ့အခါ ဒီ code ကို ထည့်ပါ။"
    )
    await cb.answer()


@router.callback_query(F.data == "promo:back")
async def promo_back(cb: CallbackQuery):
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer()
