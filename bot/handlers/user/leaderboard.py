"""/top — top spenders leaderboard."""
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services.badge_service import top_spenders
from bot.services.db import SessionLocal

logger = logging.getLogger(__name__)
router = Router(name="user_leaderboard")


@router.message(Command("top"))
async def cmd_top(message: Message):
    async with SessionLocal() as s:
        top = await top_spenders(s, limit=10)

    if not top:
        await message.answer(
            "<b>TOP SPENDERS</b>\n\n"
            "မရှိသေးပါ။"
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["<b>TOP SPENDERS</b>", ""]

    for i, (u, total) in enumerate(top):
        medal = medals[i] if i < 3 else f"{i + 1}."

        if u.username:
            masked = f"@{u.username[:1]}***"
        elif u.first_name:
            masked = f"{u.first_name[:2]}***"
        else:
            masked = f"user_{u.tg_id % 10000}"

        lines.append(f"{medal} {masked} — {total:,} Ks")

    await message.answer("\n".join(lines))
