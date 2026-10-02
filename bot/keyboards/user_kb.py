"""User-facing keyboards (reply + inline)."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# ═══ MAIN MENU ═══

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📚 Books"),
                KeyboardButton(text="🔍 Search"),
            ],
            [
                KeyboardButton(text="💰 Balance"),
                KeyboardButton(text="🎧 My Library"),
            ],
            [
                KeyboardButton(text="❤️ Wishlist"),
                KeyboardButton(text="🎁 Daily"),
            ],
            [
                KeyboardButton(text="🎟️ Promo"),
                KeyboardButton(text="👥 Referral"),
            ],
            [
                KeyboardButton(text="📚 Book Request"),
                KeyboardButton(text="☎️ Support"),
            ],
        ],
        resize_keyboard=True,
    )


# ═══ TERMS ═══

def terms_kb(
    kind: str = "none", value: str | None = None
) -> InlineKeyboardMarkup:
    payload = f"{kind}:{value or '_'}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ သဘောတူပါတယ်",
                callback_data=f"terms:accept:{payload}",
            )],
        ]
    )


# ═══ CATEGORY / BOOK ═══

def categories_kb(categories) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"📁 {c.name}",
            callback_data=f"cat:{c.id}",
        )]
        for c in categories
    ]
    rows.append([InlineKeyboardButton(
        text="📖 အားလုံး",
        callback_data="cat:all",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def books_list_kb(books) -> InlineKeyboardMarkup:
    rows = []
    for b in books:
        icon = "⏳" if b.status == "ongoing" else "✅"
        rows.append([InlineKeyboardButton(
            text=f"📚 {b.title[:35]} {icon}",
            callback_data=f"book:{b.id}",
        )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Categories",
        callback_data="books:back",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def book_detail_kb(
    book,
    episode_count: int,
    free_episodes: int = 1,
) -> InlineKeyboardMarkup:
    rows = []

    if free_episodes > 0 and episode_count >= 1:
        rows.append([InlineKeyboardButton(
            text="🆓 Episode 1 နားထောင်",
            callback_data=f"ep:free:{book.id}",
        )])

    if book.status == "finished" and book.bulk_price:
        rows.append([InlineKeyboardButton(
            text=f"📦 Bulk — {book.bulk_price:,} Ks",
            callback_data=f"bulk:{book.id}",
        )])

    rows.append([InlineKeyboardButton(
        text="🎧 Episode ဝယ်",
        callback_data=f"ep:list:{book.id}",
    )])

    rows.append([InlineKeyboardButton(
        text="⭐ Rate / Reviews",
        callback_data=f"rate:do:{book.id}",
    )])

    rows.append([InlineKeyboardButton(
        text="⬅️ Books",
        callback_data=f"cat:back:{book.category_id or 0}",
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def episode_list_kb(
    book_id: int,
    episodes,
    owned_set: set[int],
) -> InlineKeyboardMarkup:
    rows = []
    for ep in episodes:
        if ep.is_free or ep.episode_no in owned_set:
            label = f"▶️ Ep {ep.episode_no}"
            label += " 🆓" if ep.is_free else " ✅"
        else:
            label = f"🔒 Ep {ep.episode_no}"
        rows.append([InlineKeyboardButton(
            text=label,
            callback_data=f"ep:pick:{book_id}:{ep.episode_no}",
        )])

    unowned = [
        e for e in episodes
        if not e.is_free and e.episode_no not in owned_set
    ]
    if len(unowned) >= 2:
        rows.append([InlineKeyboardButton(
            text=f"🛒 Batch Buy ({len(unowned)})",
            callback_data=f"batch:start:{book_id}",
        )])

    rows.append([InlineKeyboardButton(
        text="⬅️ Book",
        callback_data=f"book:{book_id}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def batch_select_kb(
    book_id: int,
    episodes,
    selected: set[int],
    owned: set[int],
    price: int,
) -> InlineKeyboardMarkup:
    """Episode selection for batch buy."""
    rows = []

    for ep in episodes:
        if ep.is_free or ep.episode_no in owned:
            continue
        is_sel = ep.episode_no in selected
        mark = "☑️" if is_sel else "☐"
        rows.append([InlineKeyboardButton(
            text=f"{mark} Ep {ep.episode_no} — {price:,} Ks",
            callback_data=f"batch:tog:{ep.episode_no}",
        )])

    total = len(selected) * price
    if selected:
        rows.append([InlineKeyboardButton(
            text=f"✅ ဝယ်မယ် ({len(selected)}) — {total:,} Ks",
            callback_data="batch:buy",
        )])
    else:
        rows.append([InlineKeyboardButton(
            text="Episode ရွေးပါ",
            callback_data="batch:noop",
        )])

    avail = [
        e for e in episodes
        if not e.is_free and e.episode_no not in owned
    ]
    if len(selected) < len(avail):
        rows.append([InlineKeyboardButton(
            text=f"☑️ အားလုံး ရွေး ({len(avail)})",
            callback_data="batch:all",
        )])
    else:
        rows.append([InlineKeyboardButton(
            text="☐ အားလုံး ဖျက်",
            callback_data="batch:none",
        )])

    rows.append([InlineKeyboardButton(
        text="❌ Cancel",
        callback_data=f"ep:list:{book_id}",
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══ BUY ═══

def buy_confirm_kb(
    book_id: int,
    episode_no: int,
    price: int,
    promo: str = "",
) -> InlineKeyboardMarkup:
    cb = f"buy:yes:{book_id}:{episode_no}"
    if promo:
        cb += f":{promo.upper()}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ ဝယ်မယ် — {price:,} Ks",
                callback_data=cb,
            )],
            [InlineKeyboardButton(
                text="🎟️ Promo Code",
                callback_data=f"buy:promo:{book_id}:{episode_no}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"ep:list:{book_id}",
            )],
        ]
    )


def no_balance_kb(book_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="➕ Topup",
                callback_data="topup:start",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"ep:list:{book_id}",
            )],
        ]
    )


# ═══ BULK ═══

def bulk_confirm_kb(
    book_id: int, price: int, remaining: int
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ Bulk ဝယ်မယ် — {price:,} Ks",
                callback_data=f"bulk:yes:{book_id}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"book:{book_id}",
            )],
        ]
    )


def bulk_no_balance_kb(book_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="➕ Topup",
                callback_data="topup:start",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"book:{book_id}",
            )],
        ]
    )


def bulk_done_kb(book_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🎧 My Library",
                callback_data="lib:opennow",
            )],
            [InlineKeyboardButton(
                text="📚 နောက် Book",
                callback_data="cat:back:0",
            )],
        ]
    )


# ═══ LIBRARY ═══

def library_kb(books) -> InlineKeyboardMarkup:
    rows = []
    for b in books:
        icon = "⏳" if b.status == "ongoing" else "✅"
        rows.append([InlineKeyboardButton(
            text=f"📚 {b.title[:35]} {icon}",
            callback_data=f"lib:{b.id}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def library_book_kb(
    book_id: int,
    episodes,
    owned_set: set[int],
) -> InlineKeyboardMarkup:
    rows = []
    for ep in episodes:
        if ep.is_free or ep.episode_no in owned_set:
            label = f"▶️ Ep {ep.episode_no}"
            label += " 🆓" if ep.is_free else " ✅"
            rows.append([InlineKeyboardButton(
                text=label,
                callback_data=f"play:{book_id}:{ep.episode_no}",
            )])
        else:
            rows.append([InlineKeyboardButton(
                text=f"🔒 Ep {ep.episode_no} — ဝယ်ရန်",
                callback_data=f"ep:pick:{book_id}:{ep.episode_no}",
            )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Library",
        callback_data="lib:back",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══ BALANCE / TOPUP ═══

def balance_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="➕ ငွေဖြည့်",
                callback_data="topup:start",
            )],
            [InlineKeyboardButton(
                text="📜 History",
                callback_data="topup:history",
            )],
        ]
    )


def topup_amounts_kb(presets: list[int]) -> InlineKeyboardMarkup:
    rows = []
    row: list[InlineKeyboardButton] = []
    for p in presets:
        row.append(InlineKeyboardButton(
            text=f"{p:,}",
            callback_data=f"topup:amt:{p}",
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(
        text="✏️ Custom",
        callback_data="topup:custom",
    )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Back",
        callback_data="topup:back_balance",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topup_methods_kb(
    amount: int, has_kpay: bool, has_wave: bool
) -> InlineKeyboardMarkup:
    rows = []
    if has_kpay:
        rows.append([InlineKeyboardButton(
            text="📱 KPay",
            callback_data="topup:m:kpay",
        )])
    if has_wave:
        rows.append([InlineKeyboardButton(
            text="🌊 Wave",
            callback_data="topup:m:wave",
        )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Back",
        callback_data="topup:start",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topup_accounts_kb(
    method: str, accounts: list[str]
) -> InlineKeyboardMarkup:
    rows = []
    for acc in accounts:
        number, _, name = acc.partition("|")
        label = number.strip()
        if name.strip():
            label += f" — {name.strip()}"
        rows.append([InlineKeyboardButton(
            text=label,
            callback_data=f"topup:acc:{method}:{number.strip()}",
        )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Back",
        callback_data="topup:start",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topup_pending_kb(topup_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ Cancel Request",
                callback_data=f"topup:cancel:{topup_id}",
            )],
        ]
    )


def topup_rejected_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🔄 ပြန်လုပ်မယ်",
                callback_data="topup:start",
            )],
            [InlineKeyboardButton(
                text="☎️ Support",
                callback_data="support:show",
            )],
        ]
    )


# ═══ DAILY ═══

def daily_kb(can_checkin: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_checkin:
        rows.append([InlineKeyboardButton(
            text="✅ စစ်မယ်",
            callback_data="daily:do",
        )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Back",
        callback_data="daily:back",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══ REFERRAL ═══

def referral_kb(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📤 Share Link",
                url=f"https://t.me/share/url?url={link}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data="ref:back",
            )],
        ]
    )


# ═══ PROMO ═══

def promo_list_kb(codes) -> InlineKeyboardMarkup:
    rows = []
    for p in codes:
        if p.discount_type == "percent":
            label = f"🎟️ {p.code} — {p.discount_value}% off"
        else:
            label = f"🎟️ {p.code} — {p.discount_value:,} Ks off"
        rows.append([InlineKeyboardButton(
            text=label,
            callback_data=f"promo:use:{p.code}",
        )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Back",
        callback_data="promo:back",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══ WISHLIST ═══

def wishlist_kb(books) -> InlineKeyboardMarkup:
    rows = []
    for b in books:
        rows.append([InlineKeyboardButton(
            text=f"📚 {b.title[:35]}",
            callback_data=f"book:{b.id}",
        )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Back",
        callback_data="wish:back",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══ RATING ═══

def rate_stars_kb(
    book_id: int, current: int = 0
) -> InlineKeyboardMarkup:
    row = []
    for i in range(1, 6):
        mark = "⭐" if i <= current else "☆"
        row.append(InlineKeyboardButton(
            text=mark,
            callback_data=f"rate:set:{book_id}:{i}",
        ))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            row,
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"book:{book_id}",
            )],
        ]
    )


def rate_comment_kb(
    book_id: int, stars: int
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="💬 Comment ရေးမယ်",
                callback_data=f"rate:c:{book_id}:{stars}",
            )],
            [InlineKeyboardButton(
                text="⏭️ Skip",
                callback_data=f"rate:skip:{book_id}:{stars}",
            )],
        ]
    )


# ═══ BOOK REQUEST ═══

def request_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ တောင်းဆိုမယ်",
                callback_data="req:confirm",
            )],
            [InlineKeyboardButton(
                text="❌ Cancel",
                callback_data="req:cancel",
            )],
        ]
    )


# ═══ SHARED ═══

def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ Cancel",
                callback_data="cancel:all",
            )],
        ]
    )


def back_kb(
    callback: str, label: str = "⬅️ Back"
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=label, callback_data=callback
            )],
        ]
    )


def back_cancel_kb(
    back_callback: str,
    back_label: str = "⬅️ Back",
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=back_label,
                    callback_data=back_callback,
                ),
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data="cancel:all",
                ),
            ],
        ]
    )
