"""Admin — CSV export (users, purchases, ledger)."""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile

from bot.keyboards.admin_kb import export_menu_kb
from bot.services.admin_service import is_admin
from bot.services.db import SessionLocal
from bot.services.export_service import (
    export_ledger,
    export_purchases,
    export_users,
)
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_export")


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


@router.callback_query(F.data == "exp:menu")
async def export_menu(cb: CallbackQuery):
    if not await _ok(cb):
        return

    await edit_or_send(
        cb,
        "<b>EXPORT</b>\n\nCSV file ရွေးပါ:",
        reply_markup=export_menu_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "exp:users")
async def exp_users(cb: CallbackQuery):
    if not await _ok(cb):
        return

    await cb.answer("Exporting...")

    try:
        async with SessionLocal() as s:
            path = await export_users(s)

        await cb.message.answer_document(
            FSInputFile(path),
            caption=(
                f"<b>Users CSV</b>\n"
                f"<code>{path.name}</code>"
            ),
        )
    except Exception as e:
        logger.exception(f"Export users: {e}")
        await cb.message.answer(f"Export fail: {e}")


@router.callback_query(F.data == "exp:purchases")
async def exp_purchases(cb: CallbackQuery):
    if not await _ok(cb):
        return

    await cb.answer("Exporting...")

    try:
        async with SessionLocal() as s:
            path = await export_purchases(s, days=30)

        await cb.message.answer_document(
            FSInputFile(path),
            caption=(
                f"<b>Purchases (30d)</b>\n"
                f"<code>{path.name}</code>"
            ),
        )
    except Exception as e:
        logger.exception(f"Export purchases: {e}")
        await cb.message.answer(f"Export fail: {e}")


@router.callback_query(F.data == "exp:ledger")
async def exp_ledger(cb: CallbackQuery):
    if not await _ok(cb):
        return

    await cb.answer("Exporting...")

    try:
        async with SessionLocal() as s:
            path = await export_ledger(s, days=30)

        await cb.message.answer_document(
            FSInputFile(path),
            caption=(
                f"<b>Ledger (30d)</b>\n"
                f"<code>{path.name}</code>"
            ),
        )
    except Exception as e:
        logger.exception(f"Export ledger: {e}")
        await cb.message.answer(f"Export fail: {e}")
