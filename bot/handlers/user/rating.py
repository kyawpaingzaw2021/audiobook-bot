"""Rating flow — stars, comment, publish."""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.config import config
from bot.keyboards.user_kb import (
    rate_comment_kb,
    rate_stars_kb,
)
from bot.services.book_service import get_book
from bot.services.db import SessionLocal
from bot.services.purchase_service import get_user_by_tg
from bot.services.rating_service import (
    get_summary,
    get_user_rating,
    has_purchased,
    upsert_rating,
)
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="user_rating")


@router.callback_query(F.data.startswith("rate:do:"))
async def rate_do(cb: CallbackQuery):
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

        if not await has_purchased(s, user.id, book_id):
            await cb.answer(
                "ဝယ်ပြီးမှ rating ပေးလို့ရပါတယ်",
                show_alert=True,
            )
            return

        current = await get_user_rating(s, user.id, book_id)
        book = await get_book(s, book_id)
        if book is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        title = book.title

    stars = current.stars if current else 0
    stars_line = (
        "★" * stars + "☆" * (5 - stars) if stars
        else "☆☆☆☆☆"
    )

    text = (
        f"<b>RATE — {title}</b>\n\n"
        f"ကြယ် ရွေးပါ:\n\n"
        f"{stars_line}"
    )

    await edit_or_send(
        cb, text,
        reply_markup=rate_stars_kb(book_id, stars),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("rate:set:"))
async def rate_set(cb: CallbackQuery):
    try:
        _, _, bid_s, stars_s = cb.data.split(":")
        book_id = int(bid_s)
        stars = int(stars_s)
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    if not (1 <= stars <= 5):
        await cb.answer("Invalid", show_alert=True)
        return

    await edit_or_send(
        cb,
        f"<b>{'★' * stars}{'☆' * (5 - stars)}</b>\n\n"
        f"Comment ရေးမလား?",
        reply_markup=rate_comment_kb(book_id, stars),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("rate:skip:"))
async def rate_skip(cb: CallbackQuery):
    try:
        _, _, bid_s, stars_s = cb.data.split(":")
        book_id = int(bid_s)
        stars = int(stars_s)
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    await _save_from_cb(cb, book_id, stars, None)


@router.callback_query(F.data.startswith("rate:c:"))
async def rate_comment_start(cb: CallbackQuery, state):
    try:
        _, _, bid_s, stars_s = cb.data.split(":")
        book_id = int(bid_s)
        stars = int(stars_s)
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    await state.update_data(
        rate_book_id=book_id, rate_stars=stars
    )
    await state.set_state("Rate:comment")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏭️ Skip",
                    callback_data=f"rate:skip:{book_id}:{stars}",
                ),
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data="cancel:all",
                ),
            ],
        ]
    )

    await edit_or_send(
        cb,
        f"<b>{'★' * stars}</b>\n\n"
        f"Comment ရိုက်ပါ (max 500):",
        reply_markup=kb,
    )
    await cb.answer()


@router.message(StateFilter("Rate:comment"), TextInput())
async def rate_comment_save(message: Message, state):
    text = (message.text or "").strip()
    data = await state.get_data()
    book_id = data.get("rate_book_id")
    stars = data.get("rate_stars", 0)

    if not book_id or not stars:
        await state.clear()
        await message.answer(
            "Data ပျောက် — Book ပြန်ရွေးပါ"
        )
        return

    await state.clear()

    comment = None if text.lower() == "/skip" else text[:500]
    await _save_from_msg(message, book_id, stars, comment)


async def _save_from_cb(
    cb: CallbackQuery,
    book_id: int,
    stars: int,
    comment: str | None,
):
    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        if user is None:
            await cb.answer("Invalid", show_alert=True)
            return

        await upsert_rating(s, user.id, book_id, stars, comment)
        avg, cnt = await get_summary(s, book_id)
        book = await get_book(s, book_id)
        title = book.title if book else "—"

    text = (
        f"<b>Rating သိမ်းပြီ</b>\n\n"
        f"{'★' * stars}{'☆' * (5 - stars)}\n"
    )
    if comment:
        text += f"\n{comment[:200]}\n"
    text += f"\nBook avg: {avg:.1f}★ ({cnt} reviews)"

    await edit_or_send(cb, text)
    await cb.answer("ကျေးဇူး")

    if comment:
        await _post_review(
            cb.bot, cb.from_user, title, stars, comment
        )


async def _save_from_msg(
    message: Message,
    book_id: int,
    stars: int,
    comment: str | None,
):
    async with SessionLocal() as s:
        user = await get_user_by_tg(s, message.from_user.id)
        if user is None:
            await message.answer("/start ပို့ပါ")
            return

        await upsert_rating(s, user.id, book_id, stars, comment)
        avg, cnt = await get_summary(s, book_id)
        book = await get_book(s, book_id)
        title = book.title if book else "—"

    text = (
        f"<b>Rating သိမ်းပြီ</b>\n\n"
        f"{'★' * stars}{'☆' * (5 - stars)}\n"
    )
    if comment:
        text += f"\n{comment[:200]}\n"
    text += f"\nBook avg: {avg:.1f}★ ({cnt} reviews)"

    await message.answer(text)

    if comment:
        await _post_review(
            message.bot, message.from_user,
            title, stars, comment,
        )


async def _post_review(
    bot, from_user, book_title: str, stars: int, comment: str
):
    try:
        uname = from_user.username or "user"
        masked = f"@{uname[:1]}***"

        await bot.send_message(
            chat_id=config.NOTICE_CHAT_ID,
            text=(
                f"<b>Review အသစ်</b>\n\n"
                f"{masked} — {book_title}\n"
                f"{'★' * stars}{'☆' * (5 - stars)}\n\n"
                f"{comment[:200]}"
            ),
        )
    except Exception as e:
        logger.warning(f"Public review post: {e}")
