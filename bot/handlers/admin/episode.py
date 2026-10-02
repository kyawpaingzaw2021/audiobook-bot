"""Admin — add episode to existing book."""
import asyncio
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
from bot.models.user import User
from bot.services.admin_service import is_admin
from bot.services.book_service import (
    add_episode,
    count_episodes,
    get_book,
)
from bot.services.db import SessionLocal
from bot.services.wishlist_service import list_watchers
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_episode")


def _fmt(sec: int) -> str:
    if not sec:
        return "—"
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m" if h else f"{m}m {s}s"


async def _ok(event) -> bool:
    async with SessionLocal() as s:
        ok = await is_admin(s, event.from_user.id)

    if not ok:
        try:
            if isinstance(event, CallbackQuery):
                await event.answer(
                    "Access denied", show_alert=True
                )
            else:
                await event.answer("Access denied")
        except Exception:
            pass
    return ok


@router.callback_query(F.data.startswith("abk:addep2:"))
async def ep_add_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    book_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None:
            await cb.answer("Book မတွေ့", show_alert=True)
            return
        ep_count = await count_episodes(s, book_id)
        title = book.title

    await state.update_data(
        add_ep_book_id=book_id,
        add_ep_next=ep_count + 1,
    )
    await state.set_state("AddEp:file")

    await edit_or_send(
        cb,
        f"<b>Episode အသစ်</b>\n\n"
        f"{title}\n"
        f"Ep {ep_count + 1}\n\n"
        f"mp3 file ပို့ပါ (50MB အောက်)",
    )
    await cb.answer()


@router.message(StateFilter("AddEp:file"), F.audio | F.document)
async def ep_add_save(message: Message, state):
    if not await _ok(message):
        return

    if message.audio:
        file_id = message.audio.file_id
        dur = message.audio.duration or 0
        size = message.audio.file_size or 0
        name = message.audio.file_name or "audio.mp3"
    else:
        file_id = message.document.file_id
        dur = 0
        size = message.document.file_size or 0
        name = message.document.file_name or "audio.mp3"

    if not name.lower().endswith(".mp3"):
        await message.answer("mp3 file ပဲ:")
        return

    if size > 50 * 1024 * 1024:
        await message.answer(
            f"File ကြီးလွန်း "
            f"({size / 1048576:.1f} MB)\nMax 50 MB"
        )
        return

    data = await state.get_data()
    book_id = data.get("add_ep_book_id")
    ep_no = data.get("add_ep_next")

    if not book_id or not ep_no:
        await state.clear()
        await message.answer("Data ပျောက်")
        return

    storage_msg_id = None
    try:
        sent = await message.bot.forward_message(
            chat_id=config.STORAGE_CHAT_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        storage_msg_id = sent.message_id
    except Exception as e:
        logger.warning(f"Storage forward: {e}")

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None:
            await message.answer("Book မတွေ့")
            await state.clear()
            return

        try:
            await add_episode(
                s,
                book_id=book_id,
                episode_no=ep_no,
                audio_file_id=file_id,
                duration=dur,
                file_size=size,
                is_free=False,
                storage_msg_id=storage_msg_id,
            )
        except Exception as e:
            logger.exception(f"Add episode: {e}")
            await message.answer("Save မရပါ")
            await state.clear()
            return

        title = book.title
        episode_price = book.episode_price

    await state.clear()

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
        await message.bot.send_message(
            chat_id=config.NOTICE_CHAT_ID,
            text=(
                f"<b>Episode အသစ်</b>\n\n"
                f"{title}\n"
                f"Ep {ep_no} — {episode_price:,} Ks"
            ),
            reply_markup=kb,
        )
    except Exception as e:
        logger.warning(f"Notice post: {e}")

    await _notify_watchers(
        message.bot, book_id, title, ep_no, episode_price
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Book Detail",
                callback_data=f"abk:view:{book_id}",
            )],
        ]
    )

    await message.answer(
        f"<b>Ep {ep_no} ထည့်ပြီ</b>\n\n"
        f"{title}\n"
        f"{_fmt(dur)}\n"
        f"{size / 1048576:.1f} MB\n\n"
        f"Public post — OK",
        reply_markup=kb,
    )


async def _notify_watchers(
    bot, book_id: int, title: str, ep_no: int, price: int
) -> None:
    """Notify users who wishlisted the book."""
    try:
        async with SessionLocal() as s:
            user_ids = await list_watchers(s, book_id)
            if not user_ids:
                return

            r = await s.execute(
                select(User.tg_id).where(User.id.in_(user_ids))
            )
            tg_ids = [row[0] for row in r.all()]

        text = (
            f"<b>Episode အသစ်</b>\n\n"
            f"{title}\n"
            f"Ep {ep_no} — {price:,} Ks\n\n"
            f"Wishlist ထဲ ရှိစာအုပ်"
        )

        sent = 0
        for tg_id in tg_ids:
            try:
                await bot.send_message(chat_id=tg_id, text=text)
                sent += 1
                await asyncio.sleep(0.3)
            except Exception:
                pass

        logger.info(
            f"Wishlist notify: {sent}/{len(tg_ids)} for b={book_id}"
        )
    except Exception as e:
        logger.warning(f"Wishlist notify: {e}")
