"""Buy flow — free, list, pick, promo, confirm, bulk, batch."""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.keyboards.user_kb import (
    batch_select_kb,
    bulk_confirm_kb,
    bulk_done_kb,
    bulk_no_balance_kb,
    buy_confirm_kb,
    episode_list_kb,
    no_balance_kb,
)
from bot.services.book_service import get_book, list_episodes
from bot.services.db import SessionLocal
from bot.services.promo_service import redeem, validate_code
from bot.services.purchase_service import (
    bulk_buy,
    count_remaining,
    create_purchase,
    get_episode_file,
    get_user_by_tg,
    list_owned_episodes,
    owns_episode,
)
from bot.services.wallet import debit
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="user_buy")


def _fmt(sec: int) -> str:
    if not sec:
        return "—"
    m, s = divmod(sec, 60)
    return f"{m}:{s:02d}"


# ═══ FREE EPISODE ═══

@router.callback_query(F.data.startswith("ep:free:"))
async def send_free(cb: CallbackQuery):
    try:
        book_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        ep = await get_episode_file(s, book_id, 1) if book else None

        if book is None or ep is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        audio_id = ep.audio_file_id
        duration = ep.duration
        title = book.title

    try:
        await cb.message.answer_audio(
            audio=audio_id,
            caption=(
                f"<b>Episode 1</b>\n\n"
                f"{title}\n"
                f"Duration: {_fmt(duration)}"
            ),
        )
    except Exception as e:
        logger.error(f"Free ep send: {e}")
        await cb.answer("File ပို့မရပါ", show_alert=True)
        return

    await cb.answer("Playing")


# ═══ EPISODE LIST ═══

@router.callback_query(F.data.startswith("ep:list:"))
async def episode_list(cb: CallbackQuery, state):
    await state.clear()

    try:
        book_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        if book is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        episodes = await list_episodes(s, book_id)
        user = await get_user_by_tg(s, cb.from_user.id)
        owned = (
            await list_owned_episodes(s, user.id, book_id)
            if user else set()
        )
        title = book.title
        episode_price = book.episode_price

    if not episodes:
        await cb.answer("Episode မရှိပါ", show_alert=True)
        return

    text = (
        f"<b>Episodes — {title}</b>\n\n"
        f"Price: {episode_price:,} Ks/episode\n"
        f"Episode 1 — FREE\n\n"
        f"▶️ ရပြီ | 🔒 ဝယ်ရန်"
    )

    await edit_or_send(
        cb,
        text,
        reply_markup=episode_list_kb(book_id, episodes, owned),
    )
    await cb.answer()


# ═══ PICK EPISODE ═══

@router.callback_query(F.data.startswith("ep:pick:"))
async def pick_episode(cb: CallbackQuery):
    _, _, bid_s, ep_s = cb.data.split(":")
    book_id = int(bid_s)
    ep_no = int(ep_s)

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        if user is None:
            await cb.answer("/start ပို့ပါ", show_alert=True)
            return

        book = await get_book(s, book_id)
        ep = await get_episode_file(s, book_id, ep_no)
        if book is None or ep is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        if ep.is_free or await owns_episode(
            s, user.id, book_id, ep_no
        ):
            try:
                await cb.message.answer_audio(
                    audio=ep.audio_file_id,
                    caption=f"Ep {ep_no} — {book.title}",
                )
            except Exception:
                await cb.answer("File ပို့မရပါ", show_alert=True)
                return
            await cb.answer("Playing")
            return

        price = book.episode_price
        balance = user.balance
        duration = ep.duration
        title = book.title

    if balance < price:
        short = price - balance
        await edit_or_send(
            cb,
            f"<b>Balance မလုံလောက်ပါ</b>\n\n"
            f"{title}\n"
            f"Episode {ep_no}\n\n"
            f"လိုအပ်: {price:,} Ks\n"
            f"လက်ရှိ: {balance:,} Ks\n"
            f"ချို့တဲ့: {short:,} Ks",
            reply_markup=no_balance_kb(book_id),
        )
        await cb.answer()
        return

    new_bal = balance - price

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"ဝယ်မယ် — {price:,} Ks",
                callback_data=f"buy:yes:{book_id}:{ep_no}",
            )],
            [InlineKeyboardButton(
                text="Promo Code",
                callback_data=f"buy:promo:{book_id}:{ep_no}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"ep:list:{book_id}",
            )],
        ]
    )

    await edit_or_send(
        cb,
        f"<b>အတည်ပြုပါ</b>\n\n"
        f"{title}\n"
        f"Episode {ep_no}\n"
        f"Duration: {_fmt(duration)}\n\n"
        f"Price: {price:,} Ks\n\n"
        f"Balance: {balance:,} -> {new_bal:,} Ks\n\n"
        f"Digital goods — refund မရှိ",
        reply_markup=kb,
    )
    await cb.answer()


# ═══ PROMO INPUT ═══

@router.callback_query(F.data.startswith("buy:promo:"))
async def promo_input(cb: CallbackQuery, state):
    _, _, bid_s, ep_s = cb.data.split(":")
    book_id = int(bid_s)
    ep_no = int(ep_s)

    await state.update_data(
        buy_book_id=book_id, buy_ep_no=ep_no
    )
    await state.set_state("Buy:promo_code")

    from bot.keyboards.user_kb import back_cancel_kb

    await edit_or_send(
        cb,
        "<b>PROMO CODE</b>\n\nCode ရိုက်ပါ:",
        reply_markup=back_cancel_kb(
            f"buy:back:{book_id}:{ep_no}",
            "⬅️ Back",
        ),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("buy:back:"))
async def promo_back(cb: CallbackQuery, state):
    await state.clear()
    parts = cb.data.split(":")
    if len(parts) >= 4:
        bid, ep = int(parts[2]), int(parts[3])
        cb.data = f"ep:pick:{bid}:{ep}"
        await pick_episode(cb)
    else:
        await cb.answer()


@router.message(StateFilter("Buy:promo_code"), TextInput())
async def promo_apply(message: Message, state):
    text = (message.text or "").strip()

    if text.lower() == "/skip":
        await state.clear()
        await message.answer("Promo မသုံးပါ။")
        return

    data = await state.get_data()
    book_id = data.get("buy_book_id")
    ep_no = data.get("buy_ep_no")
    if not book_id or not ep_no:
        await state.clear()
        await message.answer("Data ပျောက် — Book ပြန်ရွေးပါ")
        return

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, message.from_user.id)
        book = await get_book(s, book_id)
        if user is None or book is None:
            await state.clear()
            await message.answer("မတွေ့ပါ")
            return

        price = book.episode_price
        ok, msg, discount, promo = await validate_code(
            s, text, user.id, price
        )

    await state.clear()

    if not ok:
        await message.answer(f"{msg}\n\nBook detail ပြန်ဝင်ပါ")
        return

    new_price = max(0, price - discount)

    await message.answer(
        f"<b>Promo applied</b>\n\n"
        f"<code>{promo.code}</code>\n"
        f"Discount: -{discount:,} Ks\n"
        f"Price: {price:,} -> {new_price:,} Ks",
        reply_markup=buy_confirm_kb(
            book_id, ep_no, new_price, promo.code
        ),
    )


# ═══ CONFIRM BUY ═══

@router.callback_query(F.data.startswith("buy:yes:"))
async def confirm_buy(cb: CallbackQuery):
    parts = cb.data.split(":")
    book_id = int(parts[2])
    ep_no = int(parts[3])
    promo_code = parts[4] if len(parts) > 4 else None

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        if user is None:
            await cb.answer("/start ပို့ပါ", show_alert=True)
            return

        book = await get_book(s, book_id)
        ep = await get_episode_file(s, book_id, ep_no)
        if book is None or ep is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        if await owns_episode(s, user.id, book_id, ep_no):
            await cb.answer("ဝယ်ပြီးသား", show_alert=True)
            return

        base_price = book.episode_price
        promo_obj = None
        discount = 0

        if promo_code:
            ok_p, _, discount, promo_obj = await validate_code(
                s, promo_code, user.id, base_price
            )
            if not ok_p:
                discount = 0
                promo_obj = None
                promo_code = None

        final_price = max(0, base_price - discount)

        ok, new_bal, msg = await debit(
            s,
            tg_id=cb.from_user.id,
            amount=final_price,
            type_="purchase",
            note=(
                f"{book.title} Ep {ep_no}"
                + (
                    f" [{promo_code}]"
                    if promo_code and discount else ""
                )
            ),
        )
        if not ok:
            await s.rollback()
            await edit_or_send(
                cb,
                f"{msg}",
                reply_markup=no_balance_kb(book_id),
            )
            await cb.answer()
            return

        try:
            await create_purchase(
                s,
                user_id=user.id,
                book_id=book_id,
                episode_no=ep_no,
                price_paid=final_price,
                source="single",
            )
        except ValueError:
            await s.rollback()
            await cb.answer("ဝယ်ပြီးသား", show_alert=True)
            return

        if promo_obj is not None and discount > 0:
            try:
                await redeem(
                    s,
                    promo_obj,
                    user.id,
                    discount,
                    reference=f"ep:{book_id}:{ep_no}",
                )
            except ValueError:
                logger.warning(
                    f"Promo redeem race: {promo_code}"
                )

        await s.commit()

        audio_id = ep.audio_file_id
        duration = ep.duration
        title = book.title

    try:
        await cb.message.answer_audio(
            audio=audio_id,
            caption=(
                f"<b>ဝယ်ယူပြီး</b>\n\n"
                f"{title}\n"
                f"Episode {ep_no}\n"
                f"Duration: {_fmt(duration)}\n\n"
                f"Balance: {new_bal:,} Ks"
            ),
        )
    except Exception as e:
        logger.error(f"File send: {e}")
        await cb.message.answer(
            "File ပို့ရာတွင် ပြဿနာ။ Admin ကို ဆက်သွယ်ပါ။"
        )

    await edit_or_send(
        cb,
        f"<b>ဝယ်ယူပြီး</b>\n\n"
        f"{title}\n"
        f"Episode {ep_no}\n\n"
        f"Balance: {new_bal:,} Ks",
    )

    try:
        from bot.config import config

        uname = cb.from_user.username or "user"
        masked = f"@{uname[:1]}***"
        await cb.bot.send_message(
            chat_id=config.NOTICE_CHAT_ID,
            text=(
                f"<b>ဝယ်ယူပါသည်</b>\n\n"
                f"{masked} — {title} Ep {ep_no}"
            ),
        )
    except Exception:
        pass

    try:
        from bot.services.referral_service import (
            pay_referral_bonus,
        )
        from bot.services.settings_service import (
            get_int_setting,
        )

        async with SessionLocal() as s2:
            bonus = await get_int_setting(
                s2, "referral_bonus", 200
            )
            if bonus > 0:
                await pay_referral_bonus(
                    s2, cb.from_user.id, amount=bonus
                )
    except Exception as e:
        logger.warning(f"Referral bonus: {e}")

    await cb.answer("ဝယ်ပြီး")


# ═══ BATCH BUY ═══

@router.callback_query(F.data.startswith("batch:start:"))
async def batch_start(cb: CallbackQuery, state):
    try:
        book_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        if user is None:
            await cb.answer("/start ပို့ပါ", show_alert=True)
            return

        book = await get_book(s, book_id)
        if book is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        episodes = await list_episodes(s, book_id)
        owned = await list_owned_episodes(s, user.id, book_id)
        title = book.title
        price = book.episode_price

    await state.update_data(
        batch_book_id=book_id,
        batch_selected=[],
    )
    await state.set_state("Buy:batch")

    text = (
        f"<b>BATCH BUY — {title}</b>\n\n"
        f"Episode တွေ ရွေးပါ\n"
        f"Price: {price:,} Ks/episode"
    )

    await edit_or_send(
        cb,
        text,
        reply_markup=batch_select_kb(
            book_id, episodes, set(), owned, price
        ),
    )
    await cb.answer()


@router.callback_query(
    StateFilter("Buy:batch"), F.data.startswith("batch:tog:")
)
async def batch_toggle(cb: CallbackQuery, state):
    try:
        ep_no = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    data = await state.get_data()
    book_id = data.get("batch_book_id")
    selected = set(data.get("batch_selected", []))

    if not book_id:
        await state.clear()
        await cb.answer("Data ပျောက်", show_alert=True)
        return

    if ep_no in selected:
        selected.discard(ep_no)
    else:
        selected.add(ep_no)

    await state.update_data(batch_selected=list(selected))

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        book = await get_book(s, book_id)
        if user is None or book is None:
            await state.clear()
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        episodes = await list_episodes(s, book_id)
        owned = await list_owned_episodes(s, user.id, book_id)
        title = book.title
        price = book.episode_price

    text = (
        f"<b>BATCH BUY — {title}</b>\n\n"
        f"Episode တွေ ရွေးပါ\n"
        f"Price: {price:,} Ks/episode"
    )

    await edit_or_send(
        cb,
        text,
        reply_markup=batch_select_kb(
            book_id, episodes, selected, owned, price
        ),
    )
    await cb.answer()


@router.callback_query(
    StateFilter("Buy:batch"), F.data == "batch:all"
)
async def batch_select_all(cb: CallbackQuery, state):
    data = await state.get_data()
    book_id = data.get("batch_book_id")

    if not book_id:
        await state.clear()
        await cb.answer("Data ပျောက်", show_alert=True)
        return

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        book = await get_book(s, book_id)
        if user is None or book is None:
            await state.clear()
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        episodes = await list_episodes(s, book_id)
        owned = await list_owned_episodes(s, user.id, book_id)
        title = book.title
        price = book.episode_price

    selected = {
        e.episode_no for e in episodes
        if not e.is_free and e.episode_no not in owned
    }
    await state.update_data(batch_selected=list(selected))

    text = (
        f"<b>BATCH BUY — {title}</b>\n\n"
        f"Episode တွေ ရွေးပါ\n"
        f"Price: {price:,} Ks/episode"
    )

    await edit_or_send(
        cb,
        text,
        reply_markup=batch_select_kb(
            book_id, episodes, selected, owned, price
        ),
    )
    await cb.answer(f"{len(selected)} ရွေးပြီး")


@router.callback_query(
    StateFilter("Buy:batch"), F.data == "batch:none"
)
async def batch_clear(cb: CallbackQuery, state):
    data = await state.get_data()
    book_id = data.get("batch_book_id")

    if not book_id:
        await state.clear()
        await cb.answer("Data ပျောက်", show_alert=True)
        return

    await state.update_data(batch_selected=[])

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        book = await get_book(s, book_id)
        if user is None or book is None:
            await state.clear()
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        episodes = await list_episodes(s, book_id)
        owned = await list_owned_episodes(s, user.id, book_id)
        title = book.title
        price = book.episode_price

    text = (
        f"<b>BATCH BUY — {title}</b>\n\n"
        f"Episode တွေ ရွေးပါ\n"
        f"Price: {price:,} Ks/episode"
    )

    await edit_or_send(
        cb,
        text,
        reply_markup=batch_select_kb(
            book_id, episodes, set(), owned, price
        ),
    )
    await cb.answer("ဖျက်ပြီ")


@router.callback_query(
    StateFilter("Buy:batch"), F.data == "batch:noop"
)
async def batch_noop(cb: CallbackQuery):
    await cb.answer("Episode ရွေးပါ", show_alert=True)


@router.callback_query(
    StateFilter("Buy:batch"), F.data == "batch:buy"
)
async def batch_confirm(cb: CallbackQuery, state):
    data = await state.get_data()
    book_id = data.get("batch_book_id")
    selected = data.get("batch_selected", [])

    if not book_id or not selected:
        await cb.answer("Episode မရွေးရသေးပါ", show_alert=True)
        return

    selected_sorted = sorted(selected)

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        book = await get_book(s, book_id)
        if user is None or book is None:
            await state.clear()
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        owned = await list_owned_episodes(s, user.id, book_id)
        selected_sorted = [
            ep for ep in selected_sorted if ep not in owned
        ]

        if not selected_sorted:
            await state.clear()
            await cb.answer("ဝယ်ပြီးသား", show_alert=True)
            return

        price = book.episode_price
        total = price * len(selected_sorted)
        balance = user.balance
        title = book.title

    if balance < total:
        short = total - balance
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="➕ Topup",
                    callback_data="topup:start",
                )],
                [InlineKeyboardButton(
                    text="⬅️ Back",
                    callback_data=f"batch:start:{book_id}",
                )],
            ]
        )
        await edit_or_send(
            cb,
            f"<b>Balance မလုံလောက်ပါ</b>\n\n"
            f"{title}\n"
            f"{len(selected_sorted)} episodes\n\n"
            f"လိုအပ်: {total:,} Ks\n"
            f"လက်ရှိ: {balance:,} Ks\n"
            f"ချို့တဲ့: {short:,} Ks",
            reply_markup=kb,
        )
        await cb.answer()
        return

    eps_str = ", ".join(str(e) for e in selected_sorted)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ ဝယ်မယ် — {total:,} Ks",
                callback_data="batch:execute",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"batch:start:{book_id}",
            )],
        ]
    )

    await edit_or_send(
        cb,
        f"<b>BATCH CONFIRM</b>\n\n"
        f"{title}\n"
        f"Episodes: {eps_str}\n"
        f"Count: {len(selected_sorted)}\n\n"
        f"Total: {total:,} Ks\n"
        f"Balance: {balance:,} → {balance - total:,} Ks\n\n"
        f"Digital goods — refund မရှိ",
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(
    StateFilter("Buy:batch"), F.data == "batch:execute"
)
async def batch_execute(cb: CallbackQuery, state):
    data = await state.get_data()
    book_id = data.get("batch_book_id")
    selected = data.get("batch_selected", [])

    if not book_id or not selected:
        await state.clear()
        await cb.answer("Data ပျောက်", show_alert=True)
        return

    selected_sorted = sorted(selected)

    async with SessionLocal() as s:
        user = await get_user_by_tg(s, cb.from_user.id)
        book = await get_book(s, book_id)
        if user is None or book is None:
            await state.clear()
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        owned = await list_owned_episodes(s, user.id, book_id)
        selected_sorted = [
            ep for ep in selected_sorted if ep not in owned
        ]

        if not selected_sorted:
            await state.clear()
            await cb.answer("ဝယ်ပြီးသား", show_alert=True)
            return

        price = book.episode_price
        total = price * len(selected_sorted)

        ok, new_bal, msg = await debit(
            s,
            tg_id=cb.from_user.id,
            amount=total,
            type_="purchase",
            note=f"Batch {book.title} x{len(selected_sorted)}",
        )
        if not ok:
            await s.rollback()
            await state.clear()
            await cb.answer(msg, show_alert=True)
            return

        purchased: list[int] = []
        for ep_no in selected_sorted:
            try:
                await create_purchase(
                    s,
                    user_id=user.id,
                    book_id=book_id,
                    episode_no=ep_no,
                    price_paid=price,
                    source="batch",
                )
                purchased.append(ep_no)
            except ValueError:
                pass

        if not purchased:
            await s.rollback()
            await state.clear()
            await cb.answer("ဝယ်ပြီးသား", show_alert=True)
            return

        files: list[tuple[int, str, int]] = []
        for ep_no in purchased:
            ep = await get_episode_file(s, book_id, ep_no)
            if ep is not None:
                files.append(
                    (ep.episode_no, ep.audio_file_id, ep.duration)
                )

        await s.commit()

        title = book.title

    await state.clear()

    await edit_or_send(
        cb,
        f"<b>Batch ဝယ်ပြီး</b>\n\n"
        f"{title}\n"
        f"{len(purchased)} episodes\n\n"
        f"Balance: {new_bal:,} Ks\n\n"
        f"Files ပို့နေသည်...",
    )

    sent = 0
    for ep_no, fid, dur in files:
        try:
            m, s_ = divmod(dur, 60)
            await cb.message.answer_audio(
                audio=fid,
                caption=f"{title}\nEp {ep_no} — {m}:{s_:02d}",
            )
            sent += 1
        except Exception as e:
            logger.error(f"Send ep {ep_no}: {e}")

    await cb.message.answer(
        f"<b>အားလုံး ပို့ပြီး</b>\n\n"
        f"{sent}/{len(purchased)} files",
        reply_markup=bulk_done_kb(book_id),
    )

    try:
        from bot.config import config

        uname = cb.from_user.username or "user"
        masked = f"@{uname[:1]}***"
        await cb.bot.send_message(
            chat_id=config.NOTICE_CHAT_ID,
            text=(
                f"<b>ဝယ်ယူပါသည်</b>\n\n"
                f"{masked} — {title} "
                f"({len(purchased)} eps batch)"
            ),
        )
    except Exception:
        pass

    try:
        from bot.services.referral_service import (
            pay_referral_bonus,
        )
        from bot.services.settings_service import get_int_setting

        async with SessionLocal() as s2:
            bonus = await get_int_setting(
                s2, "referral_bonus", 200
            )
            if bonus > 0:
                await pay_referral_bonus(
                    s2, cb.from_user.id, amount=bonus
                )
    except Exception:
        pass

    await cb.answer(f"ဝယ်ပြီး — {len(purchased)} eps")


# ═══ BULK ═══

@router.callback_query(F.data.startswith("bulk:"))
async def bulk_router(cb: CallbackQuery):
    parts = cb.data.split(":")
    if len(parts) == 3 and parts[1] == "yes":
        await _bulk_execute(cb, int(parts[2]))
    elif len(parts) == 2:
        await _bulk_confirm(cb, int(parts[1]))


async def _bulk_confirm(cb: CallbackQuery, book_id: int):
    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        user = await get_user_by_tg(s, cb.from_user.id)
        if book is None or user is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return
        if book.status != "finished" or not book.bulk_price:
            await cb.answer("Bulk မရပါ", show_alert=True)
            return

        remaining = await count_remaining(s, user.id, book_id)
        price = book.bulk_price
        balance = user.balance
        episode_price = book.episode_price
        book_title = book.title

    if remaining == 0:
        await cb.answer("အားလုံး ဝယ်ပြီးသား", show_alert=True)
        return

    if balance < price:
        short = price - balance
        await edit_or_send(
            cb,
            f"<b>Balance မလုံလောက်ပါ</b>\n\n"
            f"{book_title}\n"
            f"Bulk — {remaining} episodes\n\n"
            f"လိုအပ်: {price:,} Ks\n"
            f"လက်ရှိ: {balance:,} Ks\n"
            f"ချို့တဲ့: {short:,} Ks",
            reply_markup=bulk_no_balance_kb(book_id),
        )
        await cb.answer()
        return

    new_bal = balance - price
    single_total = episode_price * remaining
    savings = single_total - price

    text = (
        f"<b>BULK အတည်ပြုပါ</b>\n\n"
        f"{book_title}\n"
        f"{remaining} episodes\n\n"
        f"Price: {price:,} Ks\n\n"
        f"Balance: {balance:,} -> {new_bal:,} Ks\n\n"
    )
    if savings > 0:
        text += f"Bulk ဖြင့် {savings:,} Ks သက်သာ\n\n"
    text += "Digital goods — refund မရှိ"

    await edit_or_send(
        cb,
        text,
        reply_markup=bulk_confirm_kb(book_id, price, remaining),
    )
    await cb.answer()


async def _bulk_execute(cb: CallbackQuery, book_id: int):
    async with SessionLocal() as s:
        book = await get_book(s, book_id)
        user = await get_user_by_tg(s, cb.from_user.id)
        if book is None or user is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return
        if book.status != "finished" or not book.bulk_price:
            await cb.answer("Bulk မရပါ", show_alert=True)
            return

        remaining = await count_remaining(s, user.id, book_id)
        if remaining == 0:
            await cb.answer("ဝယ်ပြီးသား", show_alert=True)
            return

        price = book.bulk_price
        episode_price = book.episode_price

        ok, new_bal, msg = await debit(
            s,
            tg_id=cb.from_user.id,
            amount=price,
            type_="purchase",
            note=f"Bulk {book.title}",
        )
        if not ok:
            await s.rollback()
            await edit_or_send(
                cb,
                msg,
                reply_markup=bulk_no_balance_kb(book_id),
            )
            await cb.answer()
            return

        try:
            count, nos = await bulk_buy(
                s,
                user_id=user.id,
                book_id=book_id,
                price_per_ep=episode_price,
            )
        except ValueError:
            await s.rollback()
            await cb.answer("ဝယ်ပြီးသား", show_alert=True)
            return

        files: list[tuple[int, str, int]] = []
        for ep_no in nos:
            ep = await get_episode_file(s, book_id, ep_no)
            if ep is not None:
                files.append(
                    (ep.episode_no, ep.audio_file_id, ep.duration)
                )

        await s.commit()

        title = book.title

    await edit_or_send(
        cb,
        f"<b>Bulk ဝယ်ပြီး</b>\n\n"
        f"{title}\n"
        f"{count} episodes\n\n"
        f"Balance: {new_bal:,} Ks\n\n"
        f"Files ပို့နေသည်...",
    )

    sent = 0
    for ep_no, fid, dur in files:
        try:
            m, s_ = divmod(dur, 60)
            await cb.message.answer_audio(
                audio=fid,
                caption=f"{title}\nEp {ep_no} — {m}:{s_:02d}",
            )
            sent += 1
        except Exception as e:
            logger.error(f"Send ep {ep_no}: {e}")

    await cb.message.answer(
        f"<b>အားလုံး ပို့ပြီး</b>\n\n"
        f"{sent}/{count} files",
        reply_markup=bulk_done_kb(book_id),
    )

    try:
        from bot.config import config

        uname = cb.from_user.username or "user"
        masked = f"@{uname[:1]}***"
        await cb.bot.send_message(
            chat_id=config.NOTICE_CHAT_ID,
            text=(
                f"<b>ဝယ်ယူပါသည်</b>\n\n"
                f"{masked} — {title} (Bulk)"
            ),
        )
    except Exception:
        pass

    try:
        from bot.services.referral_service import (
            pay_referral_bonus,
        )
        from bot.services.settings_service import get_int_setting

        async with SessionLocal() as s2:
            bonus = await get_int_setting(
                s2, "referral_bonus", 200
            )
            if bonus > 0:
                await pay_referral_bonus(
                    s2, cb.from_user.id, amount=bonus
                )
    except Exception:
        pass

    await cb.answer()
