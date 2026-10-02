"""My Library — purchased books, play episodes."""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.keyboards.user_kb import library_book_kb, library_kb
from bot.services.badge_service import get_user_badge
from bot.services.book_service import get_book, list_episodes
from bot.services.db import SessionLocal
from bot.services.purchase_service import (
    get_episode_file,
    get_user_by_tg,
    list_owned_episodes,
    list_user_library,
    owns_episode,
)
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="user_library")


def _fmt(sec: int) -> str:
    if not sec:
        return "—"
    m, s = divmod(sec, 60)
    return f"{m}:{s:02d}"


async def _render_library(
    target,
    tg_id: int,
    *,
    edit: bool = False,
) -> None:
    """Render library menu."""
    async with SessionLocal() as s:
        user = await get_user_by_tg(s, tg_id)
        if user is None:
            msg = "/start အရင် ပို့ပါ"
            if edit:
                try:
                    await target.edit_text(msg)
                except Exception:
                    await target.answer(msg)
            else:
                await target.answer(msg)
            return

        total_spent, badge = await get_user_badge(s, user.id)
        book_ids = await list_user_library(s, user.id)

        if not book_ids:
            text = (
                "<b>My Library</b>\n\n"
                "Library မှာ စာအုပ် မရှိသေးပါ။\n\n"
                "Books -> Episode ဝယ်ပါ"
            )
            if edit:
                try:
                    await target.edit_text(text)
                except Exception:
                    await target.answer(text)
            else:
                await target.answer(text)
            return

        books = []
        for bid in book_ids:
            b = await get_book(s, bid)
            if b is not None:
                books.append(b)

    text = (
        f"<b>My Library</b>\n\n"
        f"Badge: {badge}\n"
        f"Total spent: {total_spent:,} Ks\n\n"
        f"{len(books)} books"
    )

    if edit:
        try:
            await target.edit_text(
                text, reply_markup=library_kb(books)
            )
        except Exception:
            await target.answer(
                text, reply_markup=library_kb(books)
            )
    else:
        await target.answer(text, reply_markup=library_kb(books))


@router.message(F.text == "🎧 My Library")
async def show_library(message: Message):
    await _render_library(message, message.from_user.id)


@router.callback_query(F.data == "lib:opennow")
async def lib_open(cb: CallbackQuery):
    await _render_library(
        cb.message, cb.from_user.id, edit=True
    )
    await cb.answer()


@router.callback_query(F.data == "lib:back")
async def lib_back(cb: CallbackQuery):
    await _render_library(
        cb.message, cb.from_user.id, edit=True
    )
    await cb.answer()


@router.callback_query(
    F.data.startswith("lib:")
    & ~F.data.in_({"lib:back", "lib:opennow"})
)
async def lib_book(cb: CallbackQuery):
    try:
        book_id = int(cb.data.split(":")[1])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        book = await get_book(s, book_id)
        if user is None or book is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        episodes = await list_episodes(s, book_id)
        owned = await list_owned_episodes(s, user.id, book_id)
        title = book.title

    owned_count = sum(
        1 for e in episodes
        if e.is_free or e.episode_no in owned
    )

    await edit_or_send(
        cb,
        f"<b>{title}</b>\n\n"
        f"Episodes: {owned_count}/{len(episodes)}\n\n"
        f"▶️ ရပြီ | 🔒 ဝယ်ရန်",
        reply_markup=library_book_kb(book_id, episodes, owned),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("play:"))
async def play_episode(cb: CallbackQuery):
    try:
        _, bid_s, ep_s = cb.data.split(":")
        book_id = int(bid_s)
        ep_no = int(ep_s)
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        book = await get_book(s, book_id)
        ep = await get_episode_file(s, book_id, ep_no)

        if user is None or book is None or ep is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        if not ep.is_free and not await owns_episode(
            s, user.id, book_id, ep_no
        ):
            await cb.answer("ဝယ်ရန် လိုပါ", show_alert=True)
            return

        audio_id = ep.audio_file_id
        duration = ep.duration
        title = book.title

    try:
        await cb.message.answer_audio(
            audio=audio_id,
            caption=(
                f"Ep {ep_no} — {title}\n"
                f"Duration: {_fmt(duration)}"
            ),
        )
    except Exception as e:
        logger.error(f"Re-send: {e}")
        await cb.answer("ပို့မရပါ", show_alert=True)
        return

    await cb.answer("Playing")
