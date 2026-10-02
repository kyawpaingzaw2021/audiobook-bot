"""Re-send main reply keyboard."""
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards.user_kb import main_menu_kb

logger = logging.getLogger(__name__)
router = Router(name="user_menu")


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Show the main reply keyboard."""
    await message.answer(
        "📋 Menu",
        reply_markup=main_menu_kb(),
    )
