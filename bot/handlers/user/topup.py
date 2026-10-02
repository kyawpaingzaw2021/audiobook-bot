"""Topup flow — amount, method, account, screenshot, history."""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from bot.config import config
from bot.keyboards.user_kb import (
    balance_kb,
    topup_accounts_kb,
    topup_amounts_kb,
    topup_methods_kb,
    topup_pending_kb,
    topup_rejected_kb,
)
from bot.services.db import SessionLocal
from bot.services.purchase_service import get_user_by_tg
from bot.services.settings_service import (
    get_int_setting,
    get_payment_accounts,
    get_topup_presets,
)
from bot.services.topup_service import (
    create_topup,
    get_topup,
    is_duplicate_screenshot,
    list_user_history,
    mark_cancelled,
)
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="user_topup")


async def _render_balance(target, tg_id: int, *, edit: bool):
    async with SessionLocal() as s:
        user = await get_user_by_tg(s, tg_id)
        balance = user.balance if user else 0

    text = f"<b>BALANCE</b>\n\n{balance:,} Ks"

    if edit:
        try:
            await target.edit_text(text, reply_markup=balance_kb())
        except Exception:
            await target.answer(
                text, reply_markup=balance_kb()
            )
    else:
        await target.answer(text, reply_markup=balance_kb())


@router.message(F.text == "💰 Balance")
async def show_balance(message: Message):
    await _render_balance(
        message, message.from_user.id, edit=False
    )


@router.callback_query(F.data == "topup:back_balance")
async def back_balance(cb: CallbackQuery, state):
    await state.clear()
    await _render_balance(
        cb.message, cb.from_user.id, edit=True
    )
    await cb.answer()


@router.callback_query(F.data == "topup:start")
async def topup_start(cb: CallbackQuery, state):
    await state.clear()
    async with SessionLocal() as s:
        presets = await get_topup_presets(s)

    await edit_or_send(
        cb,
        "<b>ငွေဖြည့်</b>\n\nပမာဏ ရွေးပါ:",
        reply_markup=topup_amounts_kb(presets),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("topup:amt:"))
async def pick_amount(cb: CallbackQuery, state):
    try:
        amount = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    await state.update_data(topup_amount=amount)

    async with SessionLocal() as s:
        kpay = await get_payment_accounts(s, "kpay")
        wave = await get_payment_accounts(s, "wave")

    await edit_or_send(
        cb,
        f"<b>{amount:,} Ks ဖြည့်မယ်</b>\n\nMethod ရွေးပါ:",
        reply_markup=topup_methods_kb(
            amount, bool(kpay), bool(wave)
        ),
    )
    await cb.answer()


@router.callback_query(F.data == "topup:custom")
async def custom_start(cb: CallbackQuery, state):
    from bot.keyboards.user_kb import back_cancel_kb

    await state.set_state("Topup:custom")
    await edit_or_send(
        cb,
        "<b>Custom Amount</b>\n\n"
        "Chat ထဲမှာ ပမာဏ ရိုက်ပါ (Ks)\n"
        "ဥပမာ: <code>7500</code>",
        reply_markup=back_cancel_kb("topup:start", "⬅️ Back"),
    )
    await cb.answer()


@router.message(StateFilter("Topup:custom"), TextInput())
async def custom_input(message: Message, state):
    from bot.keyboards.user_kb import back_cancel_kb

    text = (message.text or "").strip()
    try:
        amount = int(text)
    except ValueError:
        await message.answer(
            "ဂဏန်း ရိုက်ပါ:",
            reply_markup=back_cancel_kb(
                "topup:start", "⬅️ Back"
            ),
        )
        return

    async with SessionLocal() as s:
        min_a = await get_int_setting(s, "topup_min", 1000)
        max_a = await get_int_setting(s, "topup_max", 100000)

        if not (min_a <= amount <= max_a):
            await message.answer(
                f"ပမာဏ မမှန်ပါ\n"
                f"Min: {min_a:,} Ks | Max: {max_a:,} Ks"
            )
            return

        kpay = await get_payment_accounts(s, "kpay")
        wave = await get_payment_accounts(s, "wave")

    await state.update_data(topup_amount=amount)
    await state.clear()

    await message.answer(
        f"<b>{amount:,} Ks ဖြည့်မယ်</b>\n\nMethod ရွေးပါ:",
        reply_markup=topup_methods_kb(
            amount, bool(kpay), bool(wave)
        ),
    )


@router.callback_query(F.data.startswith("topup:m:"))
async def pick_method(cb: CallbackQuery):
    method = cb.data.split(":")[2]

    async with SessionLocal() as s:
        accounts = await get_payment_accounts(s, method)

    if not accounts:
        await cb.answer("Account မရှိပါ", show_alert=True)
        return

    label = "KPay" if method == "kpay" else "Wave"

    await edit_or_send(
        cb,
        f"<b>{label}</b>\n\nအကောင့် ရွေးပါ:",
        reply_markup=topup_accounts_kb(method, accounts),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("topup:acc:"))
async def pick_account(cb: CallbackQuery, state):
    parts = cb.data.split(":", 3)
    if len(parts) < 4:
        await cb.answer("Invalid", show_alert=True)
        return

    method = parts[2]
    number = parts[3]

    data = await state.get_data()
    amount = data.get("topup_amount")
    if not amount:
        await cb.answer(
            "Amount ပြန် ရွေးပါ", show_alert=True
        )
        await topup_start(cb, state)
        return

    await state.update_data(
        topup_method=method, topup_account=number
    )
    await state.set_state("Topup:awaiting_screenshot")

    label = "KPay" if method == "kpay" else "Wave"

    await edit_or_send(
        cb,
        f"<b>{label} ဖြင့် ငွေလွှဲပါ</b>\n\n"
        f"{label}: <code>{number}</code>\n"
        f"Amount: <b>{amount:,} Ks</b>\n\n"
        f"ငွေလွှဲပြီး <b>screenshot</b> ပို့ပါ",
    )
    await cb.answer()


@router.message(
    StateFilter("Topup:awaiting_screenshot"), F.photo
)
async def receive_screenshot(message: Message, state):
    data = await state.get_data()
    amount = data.get("topup_amount")
    method = data.get("topup_method")
    account = data.get("topup_account")

    if not (amount and method and account):
        await state.clear()
        await message.answer(
            "Topup data ပျောက် — /start ပြန် ပို့ပါ"
        )
        return

    photo = message.photo[-1]

    async with SessionLocal() as s:
        if await is_duplicate_screenshot(
            s, photo.file_unique_id
        ):
            await message.answer(
                "<b>Duplicate Screenshot</b>\n\n"
                "ဤ screenshot ကို ယခင်က "
                "အသုံးပြုပြီးပါပြီ။",
                reply_markup=topup_rejected_kb(),
            )
            await state.clear()
            return

        user = await get_user_by_tg(s, message.from_user.id)
        if user is None:
            await state.clear()
            await message.answer("/start ပို့ပါ")
            return

        try:
            topup = await create_topup(
                s,
                user_id=user.id,
                amount=amount,
                method=method,
                account_number=account,
                screenshot_file_id=photo.file_id,
                file_unique_id=photo.file_unique_id,
            )
            await s.commit()
        except ValueError:
            await s.rollback()
            await message.answer(
                "Duplicate Screenshot",
                reply_markup=topup_rejected_kb(),
            )
            await state.clear()
            return

        topup_id = topup.id
        username = user.username

    await state.clear()

    await message.answer(
        f"<b>TOPUP PENDING</b>\n\n"
        f"#TP-{topup_id:03d}\n"
        f"{amount:,} Ks\n"
        f"{method.upper()}\n\n"
        f"Admin verify လုပ်နေပါတယ်\n"
        f"(5 min — 2 hours)",
        reply_markup=topup_pending_kb(topup_id),
    )

    try:
        from aiogram.types import (
            InlineKeyboardButton,
            InlineKeyboardMarkup,
        )

        uname = username or "user"
        masked = f"@{uname[:1]}***"

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Panel",
                    callback_data="admin:panel",
                )]
            ]
        )

        await message.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=(
                f"<b>Topup Request</b>\n\n"
                f"#{topup_id} — {masked}\n"
                f"{amount:,} Ks\n"
                f"{method.upper()}"
            ),
            reply_markup=kb,
        )
    except Exception as e:
        logger.error(f"Admin ping: {e}")


@router.callback_query(F.data.startswith("topup:cancel:"))
async def cancel_topup(cb: CallbackQuery):
    try:
        topup_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        if user is None:
            await cb.answer("Invalid", show_alert=True)
            return

        t = await get_topup(s, topup_id)
        if (
            t is None
            or t.user_id != user.id
            or t.status != "pending"
        ):
            await cb.answer(
                "Cancel မရပါ", show_alert=True
            )
            return

        ok = await mark_cancelled(s, topup_id, user.id)

    if not ok:
        await cb.answer("Cancel မရပါ", show_alert=True)
        return

    await edit_or_send(
        cb,
        f"<b>Topup Cancelled</b>\n\n"
        f"#TP-{topup_id:03d}\n\n"
        f"Request ကို ပယ်ဖျက်လိုက်ပါပြီ။",
    )
    await cb.answer("Cancelled")


@router.callback_query(F.data == "topup:history")
async def topup_history(cb: CallbackQuery):
    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        if user is None:
            await cb.answer("Invalid", show_alert=True)
            return
        items = await list_user_history(s, user.id, limit=10)

    if not items:
        text = "<b>Topup History</b>\n\nမရှိသေးပါ။"
    else:
        icons = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "expired": "⏰",
            "cancelled": "🚫",
        }
        lines = ["<b>Topup History</b>", ""]
        for t in items:
            icon = icons.get(t.status, "?")
            date = (
                t.created_at.strftime("%d %b")
                if t.created_at else "—"
            )
            lines.append(
                f"{icon} #{t.id:03d} — {t.amount:,} Ks — {date}"
            )
        text = "\n".join(lines)

    await edit_or_send(cb, text, reply_markup=balance_kb())
    await cb.answer()
