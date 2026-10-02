"""Admin — book add flow, detail, edit, bulk, delete, repost."""
import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.config import config
from bot.keyboards.admin_kb import (
    book_cancel_kb,
    book_cover_kb,
    book_delete_confirm_kb,
    book_detail_admin_kb,
    book_edit_kb,
    book_episode_kb,
    book_status_kb,
)
from bot.services.admin_service import is_admin
from bot.services.book_service import (
    add_episode,
    count_episodes,
    create_book,
    get_book,
    list_episodes,
)
from bot.services.category_service import get_category
from bot.services.db import SessionLocal
from bot.services.settings_service import get_int_setting
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_book")


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


@router.callback_query(F.data.startswith("acat:newbook:"))
async def book_add_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    cat_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        cat = await get_category(s, cat_id)

    if cat is None:
        await cb.answer("Category မတွေ့", show_alert=True)
        return

    cat_name = cat.name

    await state.clear()
    await state.update_data(
        cat_id=cat_id, cat_name=cat_name, episodes=[]
    )
    await state.set_state("BookAdd:title")

    await edit_or_send(
        cb,
        f"<b>{cat_name}</b>\n\n"
        f"Book title ရိုက်ပါ:",
        reply_markup=book_cancel_kb(cat_id),
    )
    await cb.answer()


@router.message(StateFilter("BookAdd:title"), TextInput())
async def book_add_title(message: Message, state):
    if not await _ok(message):
        return

    title = (message.text or "").strip()[:255]
    if not title:
        await message.answer("Title ရိုက်ပါ:")
        return

    data = await state.get_data()
    cat_id = data.get("cat_id")
    cat_name = data.get("cat_name", "")

    await state.update_data(title=title)
    await state.set_state("BookAdd:author")

    await message.answer(
        f"{cat_name}\n"
        f"<b>{title}</b>\n\n"
        f"Author ရိုက်ပါ:",
        reply_markup=book_cancel_kb(cat_id),
    )


@router.message(StateFilter("BookAdd:author"), TextInput())
async def book_add_author(message: Message, state):
    if not await _ok(message):
        return

    author = (message.text or "").strip()[:255]
    if not author:
        await message.answer("Author ရိုက်ပါ:")
        return

    data = await state.get_data()
    cat_id = data.get("cat_id")

    await state.update_data(author=author)
    await state.set_state("BookAdd:cover")

    await message.answer(
        f"<b>{data['title']}</b>\n"
        f"{author}\n\n"
        f"Cover image ပို့ပါ (jpg/png)",
        reply_markup=book_cover_kb(cat_id),
    )


@router.message(StateFilter("BookAdd:cover"), F.photo)
async def book_add_cover(message: Message, state):
    if not await _ok(message):
        return

    data = await state.get_data()
    cat_id = data.get("cat_id")
    photo = message.photo[-1]

    try:
        await message.bot.send_photo(
            chat_id=config.STORAGE_CHAT_ID,
            photo=photo.file_id,
            caption=f"Cover: {data.get('title', '—')}",
        )
    except Exception as e:
        logger.warning(f"Storage cover: {e}")

    await state.update_data(cover_file_id=photo.file_id)
    await state.set_state("BookAdd:status")

    await message.answer(
        "Cover ရပြီ\n\nStatus ရွေးပါ:",
        reply_markup=book_status_kb(cat_id),
    )


@router.callback_query(F.data.startswith("abk:skipcover:"))
async def book_add_skip_cover(cb: CallbackQuery, state):
    if not await _ok(cb):
        return
    cat_id = int(cb.data.split(":")[2])

    await state.update_data(cover_file_id=None)
    await state.set_state("BookAdd:status")

    await edit_or_send(
        cb,
        "Cover skip\n\nStatus ရွေးပါ:",
        reply_markup=book_status_kb(cat_id),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("abk:status:"))
async def book_add_status(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    parts = cb.data.split(":")
    if len(parts) != 4:
        await cb.answer("Invalid", show_alert=True)
        return

    status = parts[2]
    cat_id = int(parts[3])

    if status not in ("ongoing", "finished"):
        await cb.answer("Invalid", show_alert=True)
        return

    await state.update_data(status=status)
    await state.set_state("BookAdd:ep1")

    icon = "Ongoing" if status == "ongoing" else "Finished"

    await edit_or_send(
        cb,
        f"{icon}\n\n"
        f"<b>Episode 1 (FREE)</b> ပို့ပါ\n"
        f"(mp3, 50MB အောက်)",
        reply_markup=book_cancel_kb(cat_id),
    )
    await cb.answer()


@router.message(
    StateFilter("BookAdd:ep1", "BookAdd:episodes"),
    F.audio | F.document,
)
async def book_add_episode(message: Message, state):
    if not await _ok(message):
        return

    if message.audio:
        file_id = message.audio.file_id
        duration = message.audio.duration or 0
        file_size = message.audio.file_size or 0
        file_name = message.audio.file_name or "audio.mp3"
    else:
        file_id = message.document.file_id
        duration = 0
        file_size = message.document.file_size or 0
        file_name = message.document.file_name or "audio.mp3"

    if not file_name.lower().endswith(".mp3"):
        await message.answer("mp3 file ပဲ:")
        return

    if file_size > 50 * 1024 * 1024:
        await message.answer(
            f"File ကြီးလွန်း "
            f"({file_size / 1048576:.1f} MB)\nMax 50 MB"
        )
        return

    data = await state.get_data()
    cat_id = data.get("cat_id")
    episodes = data.get("episodes", [])
    ep_no = len(episodes) + 1
    is_free = ep_no == 1

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

    episodes.append({
        "episode_no": ep_no,
        "audio_file_id": file_id,
        "duration": duration,
        "file_size": file_size,
        "is_free": is_free,
        "storage_msg_id": storage_msg_id,
    })
    await state.update_data(episodes=episodes)
    await state.set_state("BookAdd:episodes")

    total_sec = sum(e["duration"] for e in episodes)
    total_h = total_sec // 3600
    total_m = (total_sec % 3600) // 60

    free_mark = "FREE" if is_free else "PAID"

    await message.answer(
        f"<b>Ep {ep_no}</b> ရပြီ ({free_mark})\n"
        f"{_fmt(duration)} | "
        f"{file_size / 1048576:.1f} MB\n\n"
        f"Episodes: {len(episodes)} | "
        f"Total: {total_h}h {total_m}m",
        reply_markup=book_episode_kb(cat_id, ep_no),
    )


@router.callback_query(F.data.startswith("abk:addep:"))
async def book_add_more_ep(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    parts = cb.data.split(":")
    if len(parts) != 3:
        return

    cat_id = int(parts[2])
    data = await state.get_data()
    ep_count = len(data.get("episodes", []))

    await edit_or_send(
        cb,
        f"<b>Ep {ep_count + 1}</b> ပို့ပါ\n"
        f"(mp3, 50MB အောက်)",
        reply_markup=book_cancel_kb(cat_id),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("abk:save:"))
async def book_save(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    cat_id = int(cb.data.split(":")[2])
    data = await state.get_data()
    episodes = data.get("episodes", [])

    if not episodes:
        await cb.answer(
            "Episode မရှိသေးပါ", show_alert=True
        )
        return

    await edit_or_send(cb, "Saving...")

    async with SessionLocal() as s:
        default_price = await get_int_setting(
            s, "default_episode_price", 500
        )

        try:
            book = await create_book(s, {
                "title": data.get("title", "—"),
                "author": data.get("author", "—"),
                "category_id": data.get("cat_id"),
                "description": None,
                "cover_file_id": data.get("cover_file_id"),
                "episode_price": default_price,
                "bulk_price": None,
                "status": data.get("status", "ongoing"),
                "storage_chat_id": config.STORAGE_CHAT_ID,
            }, commit=False)

            for ep in episodes:
                await add_episode(
                    s,
                    book_id=book.id,
                    episode_no=ep["episode_no"],
                    audio_file_id=ep["audio_file_id"],
                    duration=ep["duration"],
                    file_size=ep["file_size"],
                    is_free=ep["is_free"],
                    storage_msg_id=ep.get("storage_msg_id"),
                    commit=False,
                )

            await s.commit()
            await s.refresh(book)

            book_id = book.id
            book_title = book.title
            book_author = book.author
            cover_id = book.cover_file_id
            bulk = book.bulk_price
            ep_count = len(episodes)
            cat_name = data.get("cat_name", "—")
            status_val = data.get("status", "ongoing")

        except Exception as e:
            await s.rollback()
            logger.exception(f"Book save: {e}")
            await edit_or_send(
                cb, "Save မရပါ — Admin log ကြည့်ပါ"
            )
            await cb.answer()
            return

    await state.clear()

    posted = False
    try:
        await _post_book_to_channel(
            cb.bot, {
                "id": book_id,
                "title": book_title,
                "author": book_author,
                "cover_file_id": cover_id,
                "episode_price": default_price,
                "bulk_price": bulk,
                "description": None,
            }, ep_count,
        )
        posted = True
    except Exception as e:
        logger.error(f"Public post: {e}")

    rows = [
        [InlineKeyboardButton(
            text="Category ပြန်",
            callback_data=f"acat:{cat_id}",
        )],
        [InlineKeyboardButton(
            text="Book Detail",
            callback_data=f"abk:view:{book_id}",
        )],
    ]

    public_text = "Public post OK" if posted else "Public post fail"

    await edit_or_send(
        cb,
        f"<b>Book Saved</b>\n\n"
        f"<b>{book_title}</b>\n"
        f"{book_author}\n"
        f"{cat_name}\n"
        f"#{book_id}\n"
        f"{status_val.title()}\n"
        f"{default_price:,} Ks/ep\n"
        f"{ep_count} episodes\n"
        f"Ep 1 — FREE\n\n"
        f"{public_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await cb.answer("Saved")


@router.callback_query(F.data.startswith("abk:cancel:"))
async def book_cancel(cb: CallbackQuery, state):
    if not await _ok(cb):
        return
    cat_id = int(cb.data.split(":")[2])
    await state.clear()

    from bot.handlers.admin.category import _render_cat

    await _render_cat(cb, cat_id)
    await cb.answer("Cancelled")


async def _render_book_admin(cb: CallbackQuery, book_id: int):
    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        episodes = await list_episodes(s, book_id)
        cat = (
            await get_category(s, book.category_id)
            if book.category_id else None
        )

        title = book.title
        author = book.author
        status = book.status
        episode_price = book.episode_price
        bulk_price = book.bulk_price
        cat_name = cat.name if cat else "—"
        ep_data = [
            {
                "no": e.episode_no,
                "dur": e.duration,
                "free": e.is_free,
            }
            for e in episodes
        ]

    status_icon = (
        "Ongoing" if status == "ongoing" else "Finished"
    )

    text = (
        f"<b>{title}</b>\n"
        f"{author}\n"
        f"Category: {cat_name}\n"
        f"Status: {status_icon}\n"
        f"Price: {episode_price:,} Ks/ep\n"
    )
    if bulk_price:
        text += f"Bulk: {bulk_price:,} Ks\n"

    text += f"\nEpisodes ({len(ep_data)}):\n"
    for e in ep_data[:10]:
        icon = "FREE" if e["free"] else "PAID"
        text += f"  Ep {e['no']} — {_fmt(e['dur'])} ({icon})\n"
    if len(ep_data) > 10:
        text += f"  ... +{len(ep_data) - 10} more\n"

    await edit_or_send(
        cb, text,
        reply_markup=book_detail_admin_kb(book_id, status),
    )


@router.callback_query(F.data.startswith("abk:view:"))
async def book_view(cb: CallbackQuery, state):
    if not await _ok(cb):
        return
    await state.clear()

    try:
        book_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        return

    await _render_book_admin(cb, book_id)
    await cb.answer()


@router.callback_query(F.data.startswith("abk:backcat:"))
async def book_back_cat(cb: CallbackQuery):
    if not await _ok(cb):
        return

    try:
        book_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        return

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        cat_id = book.category_id if book else None

    if cat_id:
        from bot.handlers.admin.category import _render_cat

        await _render_cat(cb, cat_id)
    else:
        from bot.handlers.admin.category import cat_list

        await cat_list(cb, None)
    await cb.answer()


@router.callback_query(F.data.startswith("abk:edit:"))
async def book_edit_menu(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    parts = cb.data.split(":")

    if len(parts) == 3:
        book_id = int(parts[2])
        await edit_or_send(
            cb,
            "<b>EDIT BOOK</b>\n\nဘာ ပြင်ချင်လဲ?",
            reply_markup=book_edit_kb(book_id),
        )
        await cb.answer()
        return

    field = parts[2]
    book_id = int(parts[3])

    if field == "title":
        await state.update_data(
            edit_book_id=book_id, edit_field="title"
        )
        await state.set_state("BookEdit:title")
        await edit_or_send(cb, "Title အသစ် ရိုက်ပါ:")
    elif field == "author":
        await state.update_data(
            edit_book_id=book_id, edit_field="author"
        )
        await state.set_state("BookEdit:author")
        await edit_or_send(cb, "Author အသစ် ရိုက်ပါ:")
    elif field == "cover":
        await state.update_data(
            edit_book_id=book_id, edit_field="cover"
        )
        await state.set_state("BookEdit:cover")
        await edit_or_send(cb, "Cover အသစ် ပို့ပါ:")

    await cb.answer()


@router.message(StateFilter("BookEdit:title"), TextInput())
async def book_edit_title(message: Message, state):
    if not await _ok(message):
        return

    title = (message.text or "").strip()[:255]
    if not title:
        await message.answer("Title ရိုက်ပါ:")
        return

    data = await state.get_data()
    book_id = data.get("edit_book_id")
    await state.clear()

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book:
            book.title = title
            await s.commit()

    await message.answer(f"Title: <b>{title}</b>")


@router.message(StateFilter("BookEdit:author"), TextInput())
async def book_edit_author(message: Message, state):
    if not await _ok(message):
        return

    author = (message.text or "").strip()[:255]
    if not author:
        await message.answer("Author ရိုက်ပါ:")
        return

    data = await state.get_data()
    book_id = data.get("edit_book_id")
    await state.clear()

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book:
            book.author = author
            await s.commit()

    await message.answer(f"Author: <b>{author}</b>")


@router.message(StateFilter("BookEdit:cover"), F.photo)
async def book_edit_cover(message: Message, state):
    if not await _ok(message):
        return
    photo = message.photo[-1]

    data = await state.get_data()
    book_id = data.get("edit_book_id")
    await state.clear()

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book:
            book.cover_file_id = photo.file_id
            await s.commit()

    await message.answer("Cover updated")


@router.callback_query(F.data.startswith("abk:finish:"))
async def book_finish(cb: CallbackQuery):
    if not await _ok(cb):
        return
    book_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book:
            book.status = "finished"
            book.finished_at = datetime.now(timezone.utc)
            await s.commit()

    await _render_book_admin(cb, book_id)
    await cb.answer("Finished")


@router.callback_query(F.data.startswith("abk:bulk:"))
async def book_bulk_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return
    book_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None or book.status != "finished":
            await cb.answer(
                "Finished ဆိုမှ ရ", show_alert=True
            )
            return
        ep_count = await count_episodes(s, book_id)
        title = book.title
        episode_price = book.episode_price

    paid = max(0, ep_count - 1)
    ep_total = episode_price * paid

    await state.update_data(bulk_book_id=book_id)
    await state.set_state("BookBulk:price")

    await edit_or_send(
        cb,
        f"<b>BULK PRICE</b>\n\n"
        f"{title}\n"
        f"{ep_count} episodes ({paid} paid)\n"
        f"Episode x {paid} = {ep_total:,} Ks\n\n"
        f"Bulk price ရိုက်ပါ (Ks)\n"
        f"{ep_total:,} Ks အောက်",
    )
    await cb.answer()


@router.message(StateFilter("BookBulk:price"), TextInput())
async def book_bulk_save(message: Message, state):
    if not await _ok(message):
        return

    try:
        bulk = int(
            (message.text or "").strip().replace(",", "")
        )
    except ValueError:
        await message.answer("ဂဏန်း:")
        return

    if bulk <= 0:
        await message.answer("0 ထက် ကြီး:")
        return

    data = await state.get_data()
    book_id = data.get("bulk_book_id")
    await state.clear()

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None:
            await message.answer("Book မတွေ့")
            return

        book.bulk_price = bulk
        await s.commit()
        title = book.title

    await message.answer(
        f"<b>Bulk price</b>\n\n"
        f"{title}\n"
        f"{bulk:,} Ks"
    )


@router.callback_query(F.data.startswith("abk:repost:"))
async def book_repost(cb: CallbackQuery):
    if not await _ok(cb):
        return
    book_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return
        ep_count = await count_episodes(s, book_id)
        book_data = {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "cover_file_id": book.cover_file_id,
            "episode_price": book.episode_price,
            "bulk_price": book.bulk_price,
            "description": book.description,
        }

    try:
        await _post_book_to_channel(
            cb.bot, book_data, ep_count
        )
        await cb.answer("Posted")
    except Exception as e:
        logger.error(f"Repost: {e}")
        await cb.answer("Fail", show_alert=True)


@router.callback_query(F.data.startswith("abk:del:"))
async def book_del(cb: CallbackQuery):
    if not await _ok(cb):
        return

    parts = cb.data.split(":")

    if len(parts) == 3:
        book_id = int(parts[2])

        async with SessionLocal() as s:
            book = await get_book(s, book_id)

        if book is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        await edit_or_send(
            cb,
            f"<b>Book ဖျက်မလား?</b>\n\n"
            f"{book.title}\n\n"
            f"Episodes အားလုံး + user purchases — "
            f"ဖျက်မခံရ (soft delete)\n"
            f"User side မှာ ပျောက်သွားမယ်",
            reply_markup=book_delete_confirm_kb(book_id),
        )
        await cb.answer()
        return

    if len(parts) == 4 and parts[2] == "yes":
        book_id = int(parts[3])

        async with SessionLocal() as s:
            book = await get_book(s, book_id)
            if book:
                book.is_active = False
                cat_id = book.category_id
                await s.commit()
            else:
                cat_id = None

        from bot.handlers.admin.category import _render_cat

        if cat_id:
            await _render_cat(cb, cat_id)
        else:
            await edit_or_send(cb, "Book deleted")
        await cb.answer("Deleted")


async def _post_book_to_channel(
    bot: Bot, book: dict, ep_count: int
):
    """Post book announcement to NOTICE_CHAT_ID."""
    text = (
        f"<b>Audiobook အသစ်</b>\n\n"
        f"<b>{book['title']}</b>\n"
        f"{book['author']}\n\n"
        f"Episode 1 — FREE\n"
        f"{book['episode_price']:,} Ks/episode\n"
    )
    if book.get("bulk_price"):
        text += f"Bulk: {book['bulk_price']:,} Ks\n"

    text += f"\n{ep_count} episodes"

    me = await bot.get_me()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="ဝယ်ရန်",
                url=(
                    f"https://t.me/{me.username}"
                    f"?start=book_{book['id']}"
                ),
            )]
        ]
    )

    if book.get("cover_file_id"):
        await bot.send_photo(
            chat_id=config.NOTICE_CHAT_ID,
            photo=book["cover_file_id"],
            caption=text,
            reply_markup=kb,
        )
    else:
        await bot.send_message(
            chat_id=config.NOTICE_CHAT_ID,
            text=text,
            reply_markup=kb,
        )
