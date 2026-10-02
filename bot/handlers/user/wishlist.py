"""Wishlist handlers."""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.keyboards.user_kb import wishlist_kb
from bot.services.book_service import get_book
from bot.services.db import SessionLocal
from bot.services.purchase_service import get_user_by_tg
from bot.services.wishlist_service import add, list_user, remove

logger = logging.getLogger(__name__)
router = Router(name="user_wishlist")


@router.message(F.text == "❤️ Wishlist")
async def show_wishlist(message: Message):
    async with SessionLocal() as s:
        user = await get_user_by_tg(s, message.from_user.id)
        if user is None:
            await message.answer("/start အရင် ပို့ပါ")
            return

        book_ids = await list_user(s, user.id)
        books = []
        for bid in book_ids:
            b = await get_book(s, bid)
            if b is not None and b.is_active:
                books.append(b)

    if not books:
        await message.answer(
            "<b>WISHLIST</b>\n\n"
            "မရှိသေးပါ။\n\n"
            "Books -> Book -> Save"
        )
        return

    await message.answer(
        f"<b>WISHLIST</b>\n\n"
        f"{len(books)} books",
        reply_markup=wishlist_kb(books),
    )


@router.callback_query(F.data.startswith("wish:add:"))
async def wish_add(cb: CallbackQuery):
    try:
        book_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        if user is None:
            await cb.answer("/start ပို့ပါ", show_alert=True)
            return

        book = await get_book(s, book_id)
        if book is None or not book.is_active:
            await cb.answer("Book မတွေ့ပါ", show_alert=True)
            return

        added = await add(s, user.id, book_id)

    if added:
        await cb.answer("Wishlist ထည့်ပြီ")
    else:
        await cb.answer("ရှိပြီးသား")


@router.callback_query(F.data.startswith("wish:rm:"))
async def wish_rm(cb: CallbackQuery):
    try:
        book_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        if user is None:
            await cb.answer("/start ပို့ပါ", show_alert=True)
            return
        removed = await remove(s, user.id, book_id)

    if removed:
        await cb.answer("ဖျက်ပြီ")
    else:
        await cb.answer("မတွေ့ပါ")


@router.callback_query(F.data == "wish:back")
async def wish_back(cb: CallbackQuery):
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer()
