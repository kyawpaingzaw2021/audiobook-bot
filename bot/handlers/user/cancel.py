"""Global cancel — clears any FSM state."""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

logger = logging.getLogger(__name__)
router = Router(name="user_cancel")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state):
    cur = await state.get_state()
    if cur is None:
        await message.answer("Cancel လုပ်စရာ မရှိပါ။")
        return
    await state.clear()
    await message.answer("Cancelled.")


@router.callback_query(F.data == "cancel:all")
async def cb_cancel_all(cb: CallbackQuery, state):
    cur = await state.get_state()
    logger.info(f"Cancel state={cur} user={cb.from_user.id}")
    await state.clear()

    try:
        if cb.message.photo or cb.message.document:
            base = cb.message.caption or ""
            await cb.message.edit_caption(
                caption=f"{base}\n\nCancelled",
                reply_markup=None,
            )
        else:
            base = cb.message.html_text or ""
            await cb.message.edit_text(
                f"{base}\n\nCancelled",
                reply_markup=None,
            )
    except Exception:
        pass

    await cb.answer("Cancelled")
