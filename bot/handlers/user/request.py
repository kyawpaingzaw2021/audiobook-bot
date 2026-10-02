"""Book request flow + my requests."""
import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.config import config
from bot.keyboards.user_kb import (
    back_cancel_kb,
    cancel_kb,
)
from bot.services.book_request_service import (
    create,
    find_pending_similar,
    list_user,
)
from bot.services.db import SessionLocal
from bot.services.purchase_service import get_user_by_tg
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="user_request")


@router.message(Command("request"))
@router.message(F.text == "📚 Book Request")
async def req_start(message: Message, state):
    await state.set_state("BookReq:title")
    await message.answer(
        "<b>BOOK REQUEST</b>\n\n"
        "သင်လိုချင်တဲ့ audiobook title ရိုက်ပါ:",
        reply_markup=cancel_kb(),
    )


@router.message(StateFilter("BookReq:title"), TextInput())
async def req_title(message: Message, state):
    title = (message.text or "").strip()
    if len(title) < 2 or len(title) > 255:
        await message.answer("2-255 chars:")
        return

    await state.update_data(title=title)
    await state.set_state("BookReq:author")
    await message.answer(
        f"<b>{title}</b>\n\n"
        "Author? (or /skip)",
        reply_markup=back_cancel_kb(
            "req:back_title", "⬅️ Back"
        ),
    )


@router.message(StateFilter("BookReq:author"), TextInput())
async def req_author(message: Message, state):
    text = (message.text or "").strip()
    author = None if text.lower() == "/skip" else text[:255]

    await state.update_data(author=author)
    await state.set_state("BookReq:note")
    await message.answer(
        "Note? (or /skip)",
        reply_markup=back_cancel_kb(
            "req:back_author", "⬅️ Back"
        ),
    )


@router.message(StateFilter("BookReq:note"), TextInput())
async def req_note(message: Message, state):
    text = (message.text or "").strip()
    note = None if text.lower() == "/skip" else text[:500]

    await state.update_data(note=note)
    await state.set_state("BookReq:confirm")

    data = await state.get_data()

    text_out = (
        f"<b>REQUEST SUMMARY</b>\n\n"
        f"Title: {data['title']}\n"
    )
    if data.get("author"):
        text_out += f"Author: {data['author']}\n"
    if data.get("note"):
        text_out += f"Note: {data['note'][:200]}\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ တောင်းဆိုမယ်",
                callback_data="req:confirm",
            )],
            [
                InlineKeyboardButton(
                    text="⬅️ Back",
                    callback_data="req:back_note",
                ),
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data="cancel:all",
                ),
            ],
        ]
    )

    await message.answer(text_out, reply_markup=kb)


@router.callback_query(F.data == "req:confirm")
async def req_confirm(cb: CallbackQuery, state):
    data = await state.get_data()
    if not data.get("title"):
        await cb.answer("Data ပျောက်", show_alert=True)
        return

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        if user is None:
            await cb.answer("/start", show_alert=True)
            return

        existing = await find_pending_similar(
            s, data["title"], user.id
        )
        if existing is not None:
            await state.clear()
            try:
                await cb.message.edit_text(
                    f"<b>Request ရှိပြီးသား</b>\n\n"
                    f"{data['title']}\n"
                    f"#{existing.id} — pending"
                )
            except Exception:
                pass
            await cb.answer()
            return

        try:
            req = await create(
                s,
                user_id=user.id,
                title=data["title"],
                author=data.get("author"),
                note=data.get("note"),
            )
        except Exception as e:
            logger.exception(f"Create request: {e}")
            await cb.answer("Error", show_alert=True)
            return

        req_id = req.id
        req_title = req.title

    await state.clear()

    try:
        await cb.message.edit_text(
            f"<b>Request တောင်းဆိုပြီ</b>\n\n"
            f"#{req_id}\n"
            f"{req_title}\n\n"
            f"Admin က စစ်ပြီး ထည့်ပေးပါမယ်။"
        )
    except Exception:
        pass

    await cb.answer("တောင်းဆိုပြီ")

    try:
        uname = cb.from_user.username or "user"
        masked = f"@{uname[:1]}***"

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Panel",
                    callback_data="admin:panel",
                )]
            ]
        )

        await cb.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=(
                f"<b>Book Request</b>\n\n"
                f"#{req_id} — {masked}\n"
                f"{req_title}"
            ),
            reply_markup=kb,
        )
    except Exception as e:
        logger.warning(f"Admin ping: {e}")


@router.callback_query(F.data == "req:cancel")
async def req_cancel(cb: CallbackQuery, state):
    await state.clear()
    try:
        await cb.message.edit_text("Cancelled.")
    except Exception:
        pass
    await cb.answer()


@router.message(Command("myreq"))
async def myreq(message: Message):
    async with SessionLocal() as s:
        user = await get_user_by_tg(s, message.from_user.id)
        if user is None:
            await message.answer("/start")
            return
        items = await list_user(s, user.id, limit=10)

    if not items:
        await message.answer(
            "<b>MY REQUESTS</b>\n\n"
            "မရှိသေးပါ။\n\n"
            "/request — အသစ် တောင်းရန်"
        )
        return

    icons = {
        "pending": "⏳",
        "added": "✅",
        "rejected": "❌",
    }
    lines = ["<b>MY REQUESTS</b>", ""]
    for r in items:
        icon = icons.get(r.status, "?")
        lines.append(f"{icon} #{r.id} — {r.title[:40]}")

    await message.answer("\n".join(lines))


@router.callback_query(F.data == "req:back_title")
async def back_to_title(cb: CallbackQuery, state):
    await state.set_state("BookReq:title")
    try:
        await cb.message.edit_text(
            "<b>BOOK REQUEST</b>\n\n"
            "သင်လိုချင်တဲ့ audiobook title ရိုက်ပါ:",
            reply_markup=cancel_kb(),
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "req:back_author")
async def back_to_author(cb: CallbackQuery, state):
    data = await state.get_data()
    title = data.get("title", "—")
    await state.set_state("BookReq:author")
    try:
        await cb.message.edit_text(
            f"<b>{title}</b>\n\nAuthor? (or /skip)",
            reply_markup=back_cancel_kb(
                "req:back_title", "⬅️ Back"
            ),
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "req:back_note")
async def back_to_note(cb: CallbackQuery, state):
    await state.set_state("BookReq:note")
    try:
        await cb.message.edit_text(
            "Note? (or /skip)",
            reply_markup=back_cancel_kb(
                "req:back_author", "⬅️ Back"
            ),
        )
    except Exception:
        pass
    await cb.answer()
