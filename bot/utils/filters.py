"""Shared aiogram filters."""
from aiogram.filters import BaseFilter
from aiogram.types import Message


MENU_BUTTONS: set[str] = {
    "📚 Books",
    "🔍 Search",
    "💰 Balance",
    "🎧 My Library",
    "❤️ Wishlist",
    "🎁 Daily",
    "🎟️ Promo",
    "👥 Referral",
    "📚 Book Request",
    "☎️ Support",
}


ALLOWED_INPUT_COMMANDS: set[str] = {
    "/skip",
}


class TextInput(BaseFilter):
    """Pass only if text is not empty, not menu, not command."""

    async def __call__(self, message: Message) -> bool:
        text = (message.text or "").strip()
        if not text:
            return False
        if text in MENU_BUTTONS:
            return False

        if text.lower() in ALLOWED_INPUT_COMMANDS:
            return True

        if text.startswith("/"):
            return False

        return True


class IsAdminFilter(BaseFilter):
    """Pass only if sender is an active admin."""

    async def __call__(self, message: Message) -> bool:
        from bot.services.admin_service import is_admin
        from bot.services.db import SessionLocal

        async with SessionLocal() as s:
            return await is_admin(s, message.from_user.id)
