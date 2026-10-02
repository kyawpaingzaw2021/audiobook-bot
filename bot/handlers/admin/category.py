"""Admin — category management."""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.keyboards.admin_kb import (
    back_panel_kb,
    category_back_kb,
    category_confirm_kb,
    category_list_kb,
)
from bot.services.admin_service import is_admin
from bot.services.book_service import list_books
from bot.services.category_service import (
    create_category,
    get_category,
    list_categories,
    rename_category,
    toggle_active,
)
from bot.services.db import SessionLocal
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_category")


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


@router.callback_query(F.data == "acat:list")
async def cat_list(cb: CallbackQuery, state):
    if not await _ok(cb):
        return
    await state.clear()

    async with SessionLocal() as s:
        cats = await list_categories(s, active_only=False)

    if cats:
        text = f"<b>CATEGORIES</b>\n\nTotal: {len(cats)}"
    else:
        text = "<b>CATEGORIES</b>\n\nမရှိသေးပါ။"

    await edit_or_send(
        cb, text, reply_markup=category_list_kb(cats)
    )
    await cb.answer()


async def _render_cat(cb: CallbackQuery, cat_id: int):
    async with SessionLocal() as s:
        cat = await get_category(s, cat_id)
        if cat is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        books = await list_books(
            s, category_id=cat_id, active_only=True, limit=50
        )

        cat_name = cat.name
        cat_active = cat.is_active
        book_rows = [
            {
                "id": b.id,
                "title": b.title,
                "status": b.status,
            }
            for b in books
        ]

    icon = "📁" if cat_active else "⏸️"

    text = (
        f"{icon} <b>{cat_name}</b>\n\n"
        f"Books: {len(book_rows)}"
    )

    if book_rows:
        text += "\n\n"
        for b in book_rows:
            b_icon = "⏳" if b["status"] == "ongoing" else "✅"
            text += f"{b['title'][:30]} — {b_icon}\n"

    rows = []
    for b in book_rows:
        b_icon = "⏳" if b["status"] == "ongoing" else "✅"
        rows.append([InlineKeyboardButton(
            text=f"{b['title'][:35]} {b_icon}",
            callback_data=f"abk:view:{b['id']}",
        )])

    rows.append([InlineKeyboardButton(
        text="➕ Book အသစ်",
        callback_data=f"acat:newbook:{cat_id}",
    )])

    pause_label = "⏸️ Pause" if cat_active else "▶️ Resume"
    pause_cb = (
        f"acat:pause:{cat_id}" if cat_active
        else f"acat:resume:{cat_id}"
    )
    rows.append([
        InlineKeyboardButton(
            text="✏️ Rename",
            callback_data=f"acat:rename:{cat_id}",
        ),
        InlineKeyboardButton(
            text=pause_label, callback_data=pause_cb
        ),
    ])
    rows.append([InlineKeyboardButton(
        text="🗑️ Delete",
        callback_data=f"acat:del:{cat_id}",
    )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Categories",
        callback_data="acat:list",
    )])

    await edit_or_send(
        cb, text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.regexp(r"^acat:\d+$"))
async def cat_detail(cb: CallbackQuery, state):
    if not await _ok(cb):
        return
    await state.clear()

    cat_id = int(cb.data.split(":")[1])
    await _render_cat(cb, cat_id)
    await cb.answer()


@router.callback_query(F.data == "acat:add")
async def cat_add_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    await state.set_state("CatAdd:name")
    await edit_or_send(
        cb,
        "<b>CATEGORY အသစ်</b>\n\n"
        "Category name ရိုက်ပါ:",
        reply_markup=back_panel_kb(),
    )
    await cb.answer()


@router.message(StateFilter("CatAdd:name"), TextInput())
async def cat_add_save(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    name = (message.text or "").strip()[:100]
    if not name:
        await message.answer("Name ရိုက်ပါ:")
        return

    async with SessionLocal() as s:
        try:
            cat = await create_category(s, name)
            cat_name = cat.name
            cat_id = cat.id
        except ValueError as e:
            await message.answer(f"{e}")
            return

        cats = await list_categories(s, active_only=False)

    await state.clear()

    await message.answer(
        f"<b>Category ထည့်ပြီ</b>\n\n"
        f"{cat_name}\n"
        f"#{cat_id}",
        reply_markup=category_list_kb(cats),
    )


@router.callback_query(F.data.startswith("acat:rename:"))
async def cat_rename_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    cat_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        cat = await get_category(s, cat_id)

    if cat is None:
        await cb.answer("မတွေ့ပါ", show_alert=True)
        return

    await state.update_data(rename_cat_id=cat_id)
    await state.set_state("CatRename:name")

    await edit_or_send(
        cb,
        f"<b>RENAME</b>\n\n"
        f"လက်ရှိ: <b>{cat.name}</b>\n\n"
        f"Name အသစ် ရိုက်ပါ:",
        reply_markup=category_back_kb(cat_id),
    )
    await cb.answer()


@router.message(StateFilter("CatRename:name"), TextInput())
async def cat_rename_save(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    name = (message.text or "").strip()[:100]
    if not name:
        await message.answer("Name ရိုက်ပါ:")
        return

    data = await state.get_data()
    cat_id = data.get("rename_cat_id")
    await state.clear()

    if not cat_id:
        return

    async with SessionLocal() as s:
        cat = await get_category(s, cat_id)
        if cat is None:
            await message.answer("Category မတွေ့")
            return

        old = cat.name
        try:
            await rename_category(s, cat_id, name)
        except ValueError as e:
            await message.answer(f"{e}")
            return

    await message.answer(
        f"<b>Renamed</b>\n\n"
        f"Old: {old}\n"
        f"New: <b>{name}</b>"
    )


@router.callback_query(F.data.startswith("acat:pause:"))
async def cat_pause(cb: CallbackQuery):
    if not await _ok(cb):
        return
    cat_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        await toggle_active(s, cat_id)

    await _render_cat(cb, cat_id)
    await cb.answer("Paused")


@router.callback_query(F.data.startswith("acat:resume:"))
async def cat_resume(cb: CallbackQuery):
    if not await _ok(cb):
        return
    cat_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        await toggle_active(s, cat_id)

    await _render_cat(cb, cat_id)
    await cb.answer("Resumed")


@router.callback_query(F.data.regexp(r"^acat:del:\d+$"))
async def cat_del_confirm(cb: CallbackQuery):
    if not await _ok(cb):
        return
    cat_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        cat = await get_category(s, cat_id)
        if cat is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return
        books = await list_books(
            s, category_id=cat_id, active_only=False, limit=50
        )
        cat_name = cat.name

    await edit_or_send(
        cb,
        f"<b>Category ဖျက်မလား?</b>\n\n"
        f"{cat_name}\n"
        f"Books: {len(books)}\n\n"
        f"Books တွေ — category မရှိ ဖြစ်သွားမယ် "
        f"(ဖျက်မခံရ)",
        reply_markup=category_confirm_kb(cat_id),
    )
    await cb.answer()


@router.callback_query(F.data.regexp(r"^acat:del:yes:\d+$"))
async def cat_del_yes(cb: CallbackQuery):
    if not await _ok(cb):
        return
    cat_id = int(cb.data.split(":")[3])

    from sqlalchemy import update

    from bot.models.book import Book
    from bot.models.category import Category

    async with SessionLocal() as s:
        await s.execute(
            update(Book)
            .where(Book.category_id == cat_id)
            .values(category_id=None)
        )
        await s.execute(
            update(Category)
            .where(Category.id == cat_id)
            .values(is_active=False)
        )
        await s.commit()

        cats = await list_categories(s, active_only=False)

    await edit_or_send(
        cb,
        f"<b>Category Deleted</b>\n\n"
        f"<b>CATEGORIES</b>\n\n"
        f"Total: {len(cats)}",
        reply_markup=category_list_kb(cats),
    )
    await cb.answer("Deleted")
