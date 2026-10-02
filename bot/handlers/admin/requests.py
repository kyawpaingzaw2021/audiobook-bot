"""Admin — book request review."""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from bot.config import config
from bot.keyboards.admin_kb import (
    back_panel_kb,
    request_view_kb,
    requests_admin_kb,
)
from bot.models.user import User
from bot.services.admin_service import is_admin
from bot.services.book_request_service import (
    get as get_req,
)
from bot.services.book_request_service import (
    list_pending,
    mark_added,
    mark_rejected,
)
from bot.services.book_service import get_book
from bot.services.db import SessionLocal
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_requests")


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


async def _user_tg(session, user_id: int) -> tuple[int, str | None] | None:
    """Return (tg_id, username) for a user_id."""
    r = await session.execute(
        select(User.tg_id, User.username).where(
            User.id == user_id
        )
    )
    row = r.one_or_none()
    if row is None:
        return None
    return int(row[0]), row[1]


@router.callback_query(F.data == "areq:list")
async def req_list(cb: CallbackQuery):
    if not await _ok(cb):
        return

    async with SessionLocal() as s:
        reqs = await list_pending(s, limit=30)

    if not reqs:
        await edit_or_send(
            cb,
            "<b>BOOK REQUESTS</b>\n\nPending မရှိပါ။",
            reply_markup=back_panel_kb(),
        )
        await cb.answer()
        return

    await edit_or_send(
        cb,
        f"<b>BOOK REQUESTS ({len(reqs)})</b>",
        reply_markup=requests_admin_kb(reqs),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("areq:view:"))
async def req_view(cb: CallbackQuery):
    if not await _ok(cb):
        return

    try:
        req_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        r = await get_req(s, req_id)
        if r is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        user_row = await _user_tg(s, r.user_id)

        req_data = {
            "id": r.id,
            "title": r.title,
            "author": r.author,
            "note": r.note,
            "created_at": r.created_at,
        }

    tg_id = user_row[0] if user_row else "?"
    username = user_row[1] if user_row else None

    uname = username or "user"
    masked = f"@{uname[:1]}***"

    created_str = (
        req_data["created_at"].strftime("%d %b %H:%M")
        if req_data["created_at"] else "—"
    )

    text = (
        f"<b>Request #{req_data['id']}</b>\n\n"
        f"{masked} (ID: {tg_id})\n"
        f"{created_str}\n\n"
        f"<b>{req_data['title']}</b>\n"
    )
    if req_data["author"]:
        text += f"Author: {req_data['author']}\n"
    if req_data["note"]:
        text += f"\nNote: {req_data['note'][:300]}\n"

    await edit_or_send(
        cb, text, reply_markup=request_view_kb(req_data["id"])
    )
    await cb.answer()


@router.callback_query(F.data.startswith("areq:added:"))
async def req_added_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    try:
        req_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    await state.update_data(req_id=req_id)
    await state.set_state("AdminReq:book_id")

    await edit_or_send(
        cb,
        f"<b>Request #{req_id} -> Book ID</b>\n\n"
        f"Book ID ရိုက်ပါ:\n"
        f"ဥပမာ: <code>5</code>",
        reply_markup=back_panel_kb(),
    )
    await cb.answer()


@router.message(StateFilter("AdminReq:book_id"), TextInput())
async def req_added_save(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    try:
        book_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("ဂဏန်း:")
        return

    data = await state.get_data()
    req_id = data.get("req_id")
    if not req_id:
        await state.clear()
        return

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None:
            await message.answer(
                f"Book #{book_id} မတွေ့ပါ:"
            )
            return

        r = await mark_added(
            s, req_id, message.from_user.id, book_id
        )
        if r is None:
            await message.answer("Request မတွေ့")
            await state.clear()
            return

        user_row = await _user_tg(s, r.user_id)

        book_title = book.title
        book_author = book.author
        book_price = book.episode_price
        cover_id = book.cover_file_id

    await state.clear()

    if user_row:
        try:
            await message.bot.send_message(
                chat_id=user_row[0],
                text=(
                    f"<b>သင် တောင်းခဲ့တဲ့ စာအုပ် ရောက်ပါပြီ!</b>\n\n"
                    f"{book_title}\n"
                    f"{book_author}\n\n"
                    f"{book_price:,} Ks/episode"
                ),
            )
        except Exception as e:
            logger.warning(f"User notify: {e}")

    try:
        me = await message.bot.get_me()
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="ဝယ်ရန်",
                    url=(
                        f"https://t.me/{me.username}"
                        f"?start=book_{book_id}"
                    ),
                )]
            ]
        )

        text = (
            f"<b>Request ဖြည့်ပြီ</b>\n\n"
            f"{book_title}\n"
            f"{book_author}"
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
        logger.warning(f"Public post: {e}")

    await message.answer(
        f"<b>Added</b>\n\n"
        f"Request #{req_id} -> Book #{book_id}\n"
        f"{book_title}\n\n"
        f"User notified\n"
        f"Public post"
    )


@router.callback_query(F.data.startswith("areq:rej:"))
async def req_reject_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    try:
        req_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    await state.update_data(req_id=req_id)
    await state.set_state("AdminReq:reject_reason")

    await edit_or_send(
        cb,
        f"<b>Request #{req_id} — Reject</b>\n\n"
        f"Reason ရိုက်ပါ (user ဆီ ပို့မယ်):",
        reply_markup=back_panel_kb(),
    )
    await cb.answer()


@router.message(
    StateFilter("AdminReq:reject_reason"), TextInput()
)
async def req_reject_save(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    reason = (message.text or "").strip()[:300]
    if not reason:
        await message.answer("Reason ရိုက်ပါ:")
        return

    data = await state.get_data()
    req_id = data.get("req_id")
    if not req_id:
        await state.clear()
        return

    async with SessionLocal() as s:
        r = await mark_rejected(
            s, req_id, message.from_user.id, reason
        )
        if r is None:
            await message.answer("Request မတွေ့")
            await state.clear()
            return

        user_row = await _user_tg(s, r.user_id)
        title = r.title

    await state.clear()

    if user_row:
        try:
            await message.bot.send_message(
                chat_id=user_row[0],
                text=(
                    f"<b>Request ပယ်ဖျက်ပါသည်</b>\n\n"
                    f"#{req_id}\n"
                    f"{title}\n\n"
                    f"{reason}"
                ),
            )
        except Exception:
            pass

    await message.answer(
        f"<b>Rejected</b>\n\n"
        f"Request #{req_id}\n"
        f"{reason}"
    )
