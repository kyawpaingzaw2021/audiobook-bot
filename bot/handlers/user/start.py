"""/start — terms, welcome, deep links."""
import logging

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.keyboards.user_kb import main_menu_kb, terms_kb
from bot.services.db import SessionLocal
from bot.services.referral_service import (
    find_referrer_by_code,
    register_referral,
)
from bot.services.settings_service import get_int_setting
from bot.services.user_service import accept_terms, get_or_create_user
from bot.services.wallet import credit

logger = logging.getLogger(__name__)
router = Router(name="user_start")


WELCOME_NEW = (
    "<b>Audiobook Bot</b>\n\n"
    "မင်္ဂလာပါ။\n\n"
    "ဒီ bot မှာ audiobook တွေ ဝယ်ယူ "
    "နားထောင်နိုင်ပါတယ်။\n\n"
    "<b>သတိပြုရန်</b>\n"
    "Audiobook များသည် digital goods ဖြစ်သောကြောင့် "
    "ဝယ်ယူပြီးပါက ငွေပြန်အမ်းခြင်း မရှိပါ။"
)

WELCOME_BACK = (
    "<b>Audiobook Bot</b>\n\n"
    "မင်္ဂလာပါ {name}\n\n"
    "Balance: <b>{balance:,} Ks</b>\n\n"
    "Books ကြည့်ပြီး စတင်နားထောင်ပါ။"
)


def _parse_payload(args: str | None) -> tuple[str, str | None]:
    """Parse /start deep link args."""
    if not args:
        return "none", None
    args = args.strip()
    if args.startswith("ref_"):
        return "ref", args[4:]
    if args.startswith("book_"):
        return "book", args[5:]
    return "none", None


async def _handle_payload(
    message: Message,
    user,
    kind: str,
    value: str,
    session,
) -> None:
    """Handle ref_ or book_ deep link payload."""
    if kind == "ref":
        referrer = await find_referrer_by_code(session, value)
        if referrer is None:
            await message.answer("Referral code မမှန်ပါ")
            return

        ref = await register_referral(
            session,
            referrer_id=referrer.id,
            referred_id=user.id,
            code=value.upper(),
        )
        if ref:
            await message.answer(
                "Referral မှတ်ပြီ\n\n"
                "Friend ဝယ်တဲ့အခါ bonus ရပါမယ်။"
            )
        else:
            await message.answer("Referral မှတ်ပြီးသား")

    elif kind == "book":
        try:
            book_id = int(value)
        except (ValueError, TypeError):
            return
        await _open_book_detail(message, book_id)


async def _open_book_detail(message: Message, book_id: int) -> None:
    """Open book detail from deep link."""
    from bot.keyboards.user_kb import book_detail_kb
    from bot.services.book_service import count_episodes, get_book
    from bot.services.rating_service import get_summary

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None or not book.is_active:
            await message.answer("Book မတွေ့ပါ")
            return

        ep_count = await count_episodes(s, book_id)
        avg, rcnt = await get_summary(s, book_id)

        title = book.title
        author = book.author
        status = book.status
        description = book.description
        episode_price = book.episode_price
        bulk_price = book.bulk_price
        cover_file_id = book.cover_file_id

    status_line = (
        "⏳ Ongoing" if status == "ongoing" else "✅ Finished"
    )

    text = (
        f"<b>{title}</b>\n\n"
        f"Author: {author}\n"
        f"{status_line}\n"
    )
    if rcnt > 0:
        filled = int(round(avg))
        stars = "★" * filled + "☆" * (5 - filled)
        text += f"Rating: {stars} {avg:.1f} ({rcnt})\n"

    text += "\n"
    if description:
        text += f"{description[:300]}\n\n"

    text += f"Price: {episode_price:,} Ks/episode\n"
    if status == "finished" and bulk_price:
        text += f"Bulk: {bulk_price:,} Ks\n"

    text += (
        f"\nEpisodes: {ep_count}\n"
        f"Episode 1 — FREE\n"
    )

    class _BookView:
        pass

    bv = _BookView()
    bv.id = book_id
    bv.title = title
    bv.status = status
    bv.bulk_price = bulk_price
    bv.category_id = None

    kb = book_detail_kb(bv, ep_count)

    if cover_file_id:
        try:
            await message.answer_photo(
                photo=cover_file_id,
                caption=text,
                reply_markup=kb,
            )
            return
        except Exception:
            pass

    await message.answer(text, reply_markup=kb)


async def _do_start(
    message: Message, kind: str, value: str | None
) -> None:
    """Core /start handler."""
    tg_user = message.from_user
    logger.info(f"/start kind={kind} from {tg_user.id}")

    async with SessionLocal() as session:
        user = await get_or_create_user(session, tg_user)

        if not user.accepted_terms:
            await message.answer(
                WELCOME_NEW,
                reply_markup=terms_kb(kind, value),
            )
            return

        await message.answer(
            WELCOME_BACK.format(
                name=user.first_name or "User",
                balance=user.balance,
            ),
            reply_markup=main_menu_kb(),
        )

        if kind != "none" and value:
            await _handle_payload(
                message, user, kind, value, session
            )


@router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(
    message: Message, command: CommandObject
):
    kind, value = _parse_payload(command.args)
    await _do_start(message, kind, value)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await _do_start(message, "none", None)


@router.callback_query(F.data.startswith("terms:accept"))
async def on_terms_accept(callback: CallbackQuery):
    """Handle terms acceptance + welcome bonus."""
    parts = callback.data.split(":", 3)
    kind = parts[2] if len(parts) > 2 else "none"
    value = parts[3] if len(parts) > 3 else None
    if value == "_":
        value = None

    async with SessionLocal() as session:
        user = await accept_terms(session, callback.from_user.id)
        if user is None:
            await callback.answer(
                "Error — /start ပြန် ပို့ပါ", show_alert=True
            )
            return

        bonus_msg = ""
        if user.balance == 0:
            bonus = await get_int_setting(
                session, "first_time_bonus", 100
            )
            if bonus > 0:
                ok, new_bal, _ = await credit(
                    session,
                    tg_id=user.tg_id,
                    amount=bonus,
                    type_="adjust",
                    note="Welcome bonus",
                )
                if ok:
                    await session.commit()
                    user.balance = new_bal
                    bonus_msg = (
                        f"\n\nWelcome Bonus: +{bonus:,} Ks"
                    )

        try:
            await callback.message.edit_text(
                WELCOME_BACK.format(
                    name=user.first_name or "User",
                    balance=user.balance,
                ) + bonus_msg,
            )
        except Exception:
            pass

        await callback.message.answer(
            "Books ကြည့်ရန် menu ကို သုံးပါ",
            reply_markup=main_menu_kb(),
        )

        if kind != "none" and value:
            await _handle_payload(
                callback.message, user, kind, value, session
            )

    await callback.answer("သဘောတူပြီး")
