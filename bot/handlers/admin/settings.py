"""Admin settings — payment, pricing, topup, support, channels."""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin_kb import (
    settings_back_kb,
    settings_kb,
    settings_pay_edit_kb,
    settings_pay_kb,
)
from bot.services.admin_service import is_admin
from bot.services.db import SessionLocal
from bot.services.settings_service import (
    get_payment_accounts,
    get_setting,
    set_setting,
)
from bot.utils.filters import IsAdminFilter, TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_settings")


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


def _render_pay_text(kpay: list[str], wave: list[str]) -> str:
    text = "<b>PAYMENT ACCOUNTS</b>\n\n"
    text += "<b>KPay</b>\n"
    if kpay:
        for acc in kpay:
            number, _, name = acc.partition("|")
            text += f"  {number.strip()} — {name.strip()}\n"
    else:
        text += "  (not set)\n"

    text += "\n<b>Wave</b>\n"
    if wave:
        for acc in wave:
            number, _, name = acc.partition("|")
            text += f"  {number.strip()} — {name.strip()}\n"
    else:
        text += "  (not set)\n"

    return text


@router.callback_query(F.data == "set:menu")
async def settings_menu(cb: CallbackQuery):
    if not await _ok(cb):
        return
    await edit_or_send(
        cb,
        "<b>SETTINGS</b>\n\nဘာ ပြင်ချင်လဲ?",
        reply_markup=settings_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "set:pay")
async def set_pay(cb: CallbackQuery):
    if not await _ok(cb):
        return
    async with SessionLocal() as s:
        kpay = await get_payment_accounts(s, "kpay")
        wave = await get_payment_accounts(s, "wave")

    text = _render_pay_text(kpay, wave)
    await edit_or_send(
        cb,
        text,
        reply_markup=settings_pay_kb(bool(kpay), bool(wave)),
    )
    await cb.answer()


@router.callback_query(F.data.in_({"set:pay:kpay", "set:pay:wave"}))
async def set_pay_method(cb: CallbackQuery):
    if not await _ok(cb):
        return
    method = cb.data.split(":")[2]

    async with SessionLocal() as s:
        accounts = await get_payment_accounts(s, method)

    label = "KPay" if method == "kpay" else "Wave"

    text = f"<b>{label} Accounts</b>\n\n"
    if accounts:
        for acc in accounts:
            number, _, name = acc.partition("|")
            text += f"{number.strip()} — {name.strip()}\n"
    else:
        text += "(not set)\n"

    text += (
        "\nFormat (separate with <code>;</code>):\n"
        "<code>09-111|U Kyaw; 09-222|Daw Su</code>"
    )

    await edit_or_send(
        cb, text,
        reply_markup=settings_pay_edit_kb(method),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("set:pay:edit:"))
async def set_pay_edit(cb: CallbackQuery, state):
    if not await _ok(cb):
        return
    method = cb.data.split(":")[3]
    await state.update_data(pay_method=method)
    await state.set_state("AdminSetting:pay_accounts")

    label = "KPay" if method == "kpay" else "Wave"

    await edit_or_send(
        cb,
        f"<b>{label} Accounts</b>\n\n"
        f"Format:\n"
        f"<code>09-111|U Kyaw; 09-222|Daw Su</code>\n\n"
        f"Empty: <code>none</code>",
        reply_markup=settings_back_kb("set:pay"),
    )
    await cb.answer()


@router.message(
    StateFilter("AdminSetting:pay_accounts"),
    IsAdminFilter(),
    TextInput(),
)
async def set_pay_save(message: Message, state):
    data = await state.get_data()
    method = data.get("pay_method", "kpay")

    text = (message.text or "").strip()
    if text.lower() == "none":
        text = ""

    parts = [p.strip() for p in text.split(";") if p.strip()]

    cleaned: list[str] = []
    for p in parts:
        if "|" not in p:
            await message.answer(
                "Format: <code>number|name</code>\nTry again:"
            )
            return
        cleaned.append(p)

    async with SessionLocal() as s:
        await set_setting(
            s, f"{method}_accounts", "; ".join(cleaned)
        )
        kpay = await get_payment_accounts(s, "kpay")
        wave = await get_payment_accounts(s, "wave")

    await state.clear()

    text_out = "<b>Saved</b>\n\n"
    text_out += "<b>KPay</b>\n"
    if kpay:
        for acc in kpay:
            number, _, name = acc.partition("|")
            text_out += f"  {number.strip()} — {name.strip()}\n"
    else:
        text_out += "  (not set)\n"

    text_out += "\n<b>Wave</b>\n"
    if wave:
        for acc in wave:
            number, _, name = acc.partition("|")
            text_out += f"  {number.strip()} — {name.strip()}\n"
    else:
        text_out += "  (not set)\n"

    await message.answer(
        text_out,
        reply_markup=settings_pay_kb(bool(kpay), bool(wave)),
    )


@router.callback_query(F.data == "set:price")
async def set_price(cb: CallbackQuery):
    if not await _ok(cb):
        return
    async with SessionLocal() as s:
        default = await get_setting(s, "default_episode_price")

    await edit_or_send(
        cb,
        f"<b>PRICING</b>\n\n"
        f"Default Episode Price: <b>{default} Ks</b>\n\n"
        f"Edit format:\n"
        f"<code>default=500</code>",
        reply_markup=settings_back_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "set:topup")
async def set_topup(cb: CallbackQuery):
    if not await _ok(cb):
        return
    async with SessionLocal() as s:
        presets = await get_setting(s, "topup_presets")
        mn = await get_setting(s, "topup_min")
        mx = await get_setting(s, "topup_max")
        exp = await get_setting(s, "topup_expire_hours")

    await edit_or_send(
        cb,
        f"<b>TOPUP CONFIG</b>\n\n"
        f"Presets: {presets}\n"
        f"Min: {mn} Ks\n"
        f"Max: {mx} Ks\n"
        f"Expire: {exp} h\n\n"
        f"Edit format:\n"
        f"<code>presets=1000,3000,5000</code>\n"
        f"<code>min=1000</code>\n"
        f"<code>max=100000</code>",
        reply_markup=settings_back_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "set:support")
async def set_support(cb: CallbackQuery):
    if not await _ok(cb):
        return
    async with SessionLocal() as s:
        tg = await get_setting(s, "support_telegram")
        ph = await get_setting(s, "support_phone")
        hrs = await get_setting(s, "support_hours")

    await edit_or_send(
        cb,
        f"<b>SUPPORT CONTACT</b>\n\n"
        f"Telegram: {tg}\n"
        f"Phone: {ph}\n"
        f"Hours: {hrs}\n\n"
        f"Edit format:\n"
        f"<code>telegram=@admin</code>\n"
        f"<code>phone=09-XXX</code>\n"
        f"<code>hours=9 AM - 9 PM</code>",
        reply_markup=settings_back_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "set:channels")
async def set_channels(cb: CallbackQuery):
    if not await _ok(cb):
        return
    from bot.config import config

    await edit_or_send(
        cb,
        f"<b>CHANNELS</b>\n\n"
        f"Storage: <code>{config.STORAGE_CHAT_ID}</code>\n"
        f"Notice: <code>{config.NOTICE_CHAT_ID}</code>\n\n"
        f"Change via <code>.env</code> + restart",
        reply_markup=settings_back_kb(),
    )
    await cb.answer()


@router.message(IsAdminFilter(), F.text.regexp(r"^[a-z_]+=\S.*$"))
async def settings_keyvalue_input(message: Message):
    text = (message.text or "").strip()
    if "=" not in text:
        return

    key, value = text.split("=", 1)
    key = key.strip()
    value = value.strip()

    allowed = {
        "telegram": "support_telegram",
        "phone": "support_phone",
        "hours": "support_hours",
        "email": "support_email",
        "default": "default_episode_price",
        "presets": "topup_presets",
        "min": "topup_min",
        "max": "topup_max",
        "expire": "topup_expire_hours",
        "daily": "daily_reward",
        "bonus": "first_time_bonus",
        "refbonus": "referral_bonus",
        "reengage": "reengage_days",
    }

    real_key = allowed.get(key)
    if not real_key:
        return

    async with SessionLocal() as s:
        await set_setting(s, real_key, value)

    await message.answer(
        f"<b>Saved</b>\n\n"
        f"Key: <b>{real_key}</b>\n"
        f"Value: <code>{value}</code>"
    )
