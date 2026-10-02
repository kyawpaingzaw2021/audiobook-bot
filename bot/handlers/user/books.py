"""Book browsing — categories, list, detail."""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.keyboards.user_kb import (
    book_detail_kb,
    books_list_kb,
    categories_kb,
)
from bot.services.book_service import (
    count_episodes,
    get_book,
    list_books,
)
from bot.services.category_service import (
    get_category,
    list_categories,
)
from bot.services.db import SessionLocal
from bot.services.rating_service import get_summary
from bot.utils.messaging import edit_or_send, send_clean

logger = logging.getLogger(__name__)
router = Router(name="user_books")


@router.message(F.text == "📚 Books")
async def show_categories(message: Message):
    async with SessionLocal() as s:
        cats = await list_categories(s)

    if not cats:
        await send_clean(
            message,
            "<b>Books</b>\n\nCategory မရှိသေးပါ။",
        )
        return

    await send_clean(
        message,
        "<b>Categories</b>\n\nရွေးပါ:",
        reply_markup=categories_kb(cats),
    )


@router.callback_query(F.data == "books:back")
async def back_to_categories(cb: CallbackQuery):
    async with SessionLocal() as s:
        cats = await list_categories(s)

    await edit_or_send(
        cb,
        "<b>Categories</b>\n\nရွေးပါ:",
        reply_markup=categories_kb(cats) if cats else None,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("cat:"))
async def show_books(cb: CallbackQuery):
    parts = cb.data.split(":")
    tag = parts[1] if len(parts) > 1 else "all"

    async with SessionLocal() as s:
        if tag == "all":
            books = await list_books(s)
            title = "Books — All"
        elif tag == "back":
            real_id = int(parts[2]) if len(parts) > 2 else 0
            if real_id:
                books = await list_books(s, category_id=real_id)
                cat = await get_category(s, real_id)
                title = cat.name if cat else "Books"
            else:
                books = await list_books(s)
                title = "Books"
        else:
            try:
                cid = int(tag)
            except ValueError:
                await cb.answer("Invalid", show_alert=True)
                return
            books = await list_books(s, category_id=cid)
            cat = await get_category(s, cid)
            title = cat.name if cat else "Books"

        if not books:
            cats = await list_categories(s)

    if not books:
        await edit_or_send(
            cb,
            f"<b>{title}</b>\n\nBook မရှိသေးပါ။",
            reply_markup=categories_kb(cats),
        )
        await cb.answer()
        return

    await edit_or_send(
        cb,
        f"<b>{title}</b>\n\n{len(books)} books",
        reply_markup=books_list_kb(books),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("book:"))
async def show_book_detail(cb: CallbackQuery):
    try:
        book_id = int(cb.data.split(":")[1])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None:
            await cb.answer("Book မတွေ့ပါ", show_alert=True)
            return

        ep_count = await count_episodes(s, book_id)
        avg, rcnt = await get_summary(s, book_id)

        title = book.title
        author = book.author
        status = book.status
        description = book.description
        episode_price = book.episode_price
        bulk_price = book.bulk_price
        cover_file_id = book.cover_file_id
        category_id = book.category_id

    status_line = (
        "⏳ Ongoing" if status == "ongoing" else "✅ Finished"
    )

    text = (
        f"<b>{title}</b>\n\n"
        f"Author: {author}\n"
        f"{status_line}\n"
    )
    if rcnt > 0:
        filled = int(round(avg))
        stars = "★" * filled + "☆" * (5 - filled)
        text += f"Rating: {stars} {avg:.1f} ({rcnt})\n"

    text += "\n"
    if description:
        text += f"{description[:300]}\n\n"

    text += f"Price: {episode_price:,} Ks/episode\n"
    if status == "finished" and bulk_price:
        text += f"Bulk: {bulk_price:,} Ks\n"

    text += (
        f"\nEpisodes: {ep_count}\n"
        f"Episode 1 — FREE\n"
    )

    class _BookView:
        pass

    bv = _BookView()
    bv.id = book_id
    bv.title = title
    bv.status = status
    bv.bulk_price = bulk_price
    bv.category_id = category_id

    kb = book_detail_kb(bv, ep_count)

    if cover_file_id:
        await edit_or_send(
            cb, text, reply_markup=kb, photo=cover_file_id
        )
    else:
        await edit_or_send(cb, text, reply_markup=kb)

    await cb.answer()
