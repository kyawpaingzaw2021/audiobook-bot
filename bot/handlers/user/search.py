"""Book search handler."""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from bot.keyboards.user_kb import books_list_kb, cancel_kb
from bot.services.book_service import search_books
from bot.services.db import SessionLocal
from bot.utils.filters import TextInput

logger = logging.getLogger(__name__)
router = Router(name="user_search")


@router.message(F.text == "🔍 Search")
async def search_start(message: Message, state):
    await state.set_state("Search:query")
    await message.answer(
        "<b>SEARCH</b>\n\n"
        "Book title သို့ author ရိုက်ပါ:",
        reply_markup=cancel_kb(),
    )


@router.message(StateFilter("Search:query"), TextInput())
async def search_do(message: Message, state):
    query = (message.text or "").strip()

    if len(query) < 2:
        await message.answer(
            "အနည်းဆုံး ၂ လုံး ရိုက်ပါ:",
            reply_markup=cancel_kb(),
        )
        return

    if len(query) > 100:
        await message.answer(
            "ရှည်လွန်းပါ (100 chars max):",
            reply_markup=cancel_kb(),
        )
        return

    await state.clear()

    async with SessionLocal() as s:
        books = await search_books(s, query, limit=15)

    if not books:
        await message.answer(
            f"Search: <code>{query}</code>\n\n"
            "ရှာတွေ့မှု မရှိပါ။\n\n"
            "စာလုံး အနည်းဆုံး ၂ လုံး ထည့်ကြည့်ပါ။"
        )
        return

    await message.answer(
        f"Search: <code>{query}</code>\n\n"
        f"{len(books)} book တွေ့ပါတယ်:",
        reply_markup=books_list_kb(books),
    )
