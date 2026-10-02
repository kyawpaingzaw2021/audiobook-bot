"""Admin — books list, book detail, finish flow."""
import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import func, select

from bot.config import config
from bot.keyboards.admin_kb import back_panel_kb
from bot.models.purchase import Purchase
from bot.services.admin_service import is_admin
from bot.services.book_service import (
    count_episodes,
    get_book,
    list_books,
)
from bot.services.db import SessionLocal
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_finish")


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


@router.callback_query(F.data == "admin:books")
async def admin_books(cb: CallbackQuery):
    if not await _ok(cb):
        return

    async with SessionLocal() as s:
        books = await list_books(s, active_only=True, limit=50)
        rows_data = [
            {
                "id": b.id,
                "title": b.title,
                "status": b.status,
            }
            for b in books
        ]

    rows = []
    for b in rows_data:
        icon = "⏳" if b["status"] == "ongoing" else "✅"
        rows.append([InlineKeyboardButton(
            text=f"{icon} #{b['id']} {b['title'][:25]}",
            callback_data=f"abk:{b['id']}",
        )])

    rows.append([InlineKeyboardButton(
        text="⬅️ Panel",
        callback_data="admin:panel",
    )])

    text = (
        f"<b>BOOKS</b>\n\n"
        f"Total: {len(rows_data)}"
    )

    await edit_or_send(
        cb, text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await cb.answer()


@router.callback_query(F.data.regexp(r"^abk:\d+$"))
async def admin_book_detail(cb: CallbackQuery):
    if not await _ok(cb):
        return

    try:
        book_id = int(cb.data.split(":")[1])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        ep_count = await count_episodes(s, book_id)

        r = await s.execute(
            select(func.count(Purchase.id)).where(
                Purchase.book_id == book_id
            )
        )
        purchase_count = int(r.scalar() or 0)

        title = book.title
        author = book.author
        status = book.status
        episode_price = book.episode_price
        bulk_price = book.bulk_price

    status_line = (
        "⏳ Ongoing" if status == "ongoing" else "✅ Finished"
    )

    text = (
        f"<b>{title}</b>\n\n"
        f"{author}\n"
        f"Status: {status_line}\n"
        f"Price: {episode_price:,} Ks/ep\n"
    )
    if bulk_price:
        text += f"Bulk: {bulk_price:,} Ks\n"

    text += (
        f"\nEpisodes: {ep_count}\n"
        f"Purchases: {purchase_count}"
    )

    rows = []

    if status == "ongoing":
        rows.append([InlineKeyboardButton(
            text="Finish လုပ်မယ် (Bulk price)",
            callback_data=f"abk:fin:{book_id}",
        )])

    rows.append([InlineKeyboardButton(
        text="➕ Episode အသစ် ထည့်",
        callback_data=f"abk:addep2:{book_id}",
    )])
    rows.append([InlineKeyboardButton(
        text="✏️ Book Detail (Edit)",
        callback_data=f"abk:view:{book_id}",
    )])

    rows.append([
        InlineKeyboardButton(
            text="📢 Re-post",
            callback_data=f"abk:repost:{book_id}",
        ),
        InlineKeyboardButton(
            text="🗑️ Delete",
            callback_data=f"abk:del:{book_id}",
        ),
    ])

    rows.append([InlineKeyboardButton(
        text="⬅️ Books",
        callback_data="admin:books",
    )])

    await edit_or_send(
        cb, text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("abk:fin:"))
async def admin_finish(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    book_id = int(cb.data.split(":")[2])

    await state.update_data(finish_book_id=book_id)
    await state.set_state("AdminFinish:bulk_price")

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        ep_count = await count_episodes(s, book_id)
        title = book.title
        episode_price = book.episode_price

    paid = max(0, ep_count - 1)
    ep_total = episode_price * paid

    await edit_or_send(
        cb,
        f"<b>FINISH — {title}</b>\n\n"
        f"Episodes: {ep_count} ({paid} paid)\n"
        f"Episode price x {paid} = {ep_total:,} Ks\n\n"
        f"Bulk price ရိုက်ပါ (Ks)\n"
        f"{ep_total:,} Ks အောက် ဖြစ်ရမယ်",
        reply_markup=back_panel_kb(),
    )
    await cb.answer()


@router.message(
    StateFilter("AdminFinish:bulk_price"), TextInput()
)
async def admin_finish_save(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    try:
        bulk = int(
            (message.text or "").strip().replace(",", "")
        )
    except ValueError:
        await message.answer("ဂဏန်း:")
        return

    data = await state.get_data()
    book_id = data.get("finish_book_id")
    if not book_id:
        await state.clear()
        return

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None:
            await message.answer("Book မတွေ့ပါ")
            await state.clear()
            return

        ep_count = await count_episodes(s, book_id)
        paid = max(0, ep_count - 1)
        ep_total = book.episode_price * paid

        if bulk <= 0 or (paid > 0 and bulk >= ep_total):
            await message.answer(
                f"Bulk ({bulk:,}) က 0 ထက် ကြီး၊ "
                f"{ep_total:,} အောက် ဖြစ်ရမယ်:"
            )
            return

        book.status = "finished"
        book.bulk_price = bulk
        book.finished_at = datetime.now(timezone.utc)
        await s.commit()
        await s.refresh(book)

        book_id_val = book.id
        book_title = book.title
        book_author = book.author
        cover_id = book.cover_file_id

    await state.clear()

    try:
        me = await message.bot.get_me()
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"Bulk ဝယ် — {bulk:,} Ks",
                    url=(
                        f"https://t.me/{me.username}"
                        f"?start=book_{book_id_val}"
                    ),
                )]
            ]
        )

        text = (
            f"<b>{book_title} — ပြီးဆုံးပါပြီ</b>\n\n"
            f"{book_author}\n\n"
            f"Bulk: <b>{bulk:,} Ks</b>\n"
            f"{ep_count} episodes\n"
        )

        if cover_id:
            await message.bot.send_photo(
                chat_id=config.NOTICE_CHAT_ID,
                photo=cover_id,
                caption=text,
                reply_markup=kb,
            )
        else:
            await message.bot.send_message(
                chat_id=config.NOTICE_CHAT_ID,
                text=text,
                reply_markup=kb,
            )
    except Exception as e:
        logger.error(f"Finish post: {e}")

    await message.answer(
        f"<b>FINISHED</b>\n\n"
        f"{book_title}\n"
        f"Bulk: {bulk:,} Ks\n\n"
        f"Public post — OK"
    )
