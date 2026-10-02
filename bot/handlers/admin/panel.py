"""Admin panel — /panel + back/refresh."""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin_kb import panel_kb
from bot.services.admin_service import ensure_super_admin, is_admin
from bot.services.db import SessionLocal
from bot.services.topup_service import count_pending

logger = logging.getLogger(__name__)
router = Router(name="admin_panel")


async def _render_panel(target, *, edit: bool = False):
    """Render admin panel."""
    async with SessionLocal() as s:
        pending = await count_pending(s)

    text = (
        f"<b>ADMIN PANEL</b>\n\n"
        f"Pending topups: {pending}"
    )
    kb = panel_kb(pending)

    if edit:
        try:
            await target.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass
    await target.answer(text, reply_markup=kb)


@router.message(Command("panel"))
async def cmd_panel(message: Message):
    async with SessionLocal() as s:
        await ensure_super_admin(s)
        if not await is_admin(s, message.from_user.id):
            await message.answer("Admin မဟုတ်ပါ။")
            return

    await _render_panel(message)


@router.callback_query(F.data == "admin:panel")
async def back_panel(cb: CallbackQuery):
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return

    await _render_panel(cb.message, edit=True)
    await cb.answer()


@router.callback_query(F.data == "admin:refresh")
async def refresh_panel(cb: CallbackQuery):
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return

    await _render_panel(cb.message, edit=True)
    await cb.answer("Refreshed")
