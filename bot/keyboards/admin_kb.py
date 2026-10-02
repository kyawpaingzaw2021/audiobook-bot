"""Admin-facing keyboards."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


# ═══ PANEL ═══

def panel_kb(pending_count: int = 0) -> InlineKeyboardMarkup:
    topup_label = (
        f"💰 Topup ({pending_count})" if pending_count
        else "💰 Topup"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=topup_label,
                    callback_data="admin:topups",
                ),
                InlineKeyboardButton(
                    text="📁 Categories",
                    callback_data="acat:list",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📚 Books",
                    callback_data="admin:books",
                ),
                InlineKeyboardButton(
                    text="📚 Requests",
                    callback_data="areq:list",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎟️ Promos",
                    callback_data="apromo:list",
                ),
                InlineKeyboardButton(
                    text="📊 Analytics",
                    callback_data="ana:menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👥 Users",
                    callback_data="auser:menu",
                ),
                InlineKeyboardButton(
                    text="📢 Bulk",
                    callback_data="abulk:menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📥 Export",
                    callback_data="exp:menu",
                ),
                InlineKeyboardButton(
                    text="⚙️ Settings",
                    callback_data="set:menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Refresh",
                    callback_data="admin:refresh",
                ),
            ],
        ]
    )


def back_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ Panel",
                callback_data="admin:panel",
            )],
        ]
    )


# ═══ TOPUP ═══

def topup_list_kb(topups) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"#{t.id} — {t.amount:,} Ks — {t.method.upper()}",
            callback_data=f"adm:tp:{t.id}",
        )]
        for t in topups
    ]
    rows.append([
        InlineKeyboardButton(
            text="⬅️ Panel",
            callback_data="admin:panel",
        ),
        InlineKeyboardButton(
            text="🔄 Refresh",
            callback_data="admin:topups",
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topup_detail_kb(topup_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Approve",
                callback_data=f"adm:tp:ap:{topup_id}",
            )],
            [InlineKeyboardButton(
                text="❌ Reject",
                callback_data=f"adm:tp:rj:{topup_id}",
            )],
            [InlineKeyboardButton(
                text="✏️ Adjust",
                callback_data=f"adm:tp:adj:{topup_id}",
            )],
            [InlineKeyboardButton(
                text="⬅️ List",
                callback_data="admin:topups",
            )],
        ]
    )


def topup_approve_confirm_kb(
    topup_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Yes, Approve",
                callback_data=f"adm:tp:ap:yes:{topup_id}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"adm:tp:{topup_id}",
            )],
        ]
    )


def topup_reject_reasons_kb(
    topup_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📸 Screenshot မရှင်း",
                callback_data=f"adm:tp:rj:r1:{topup_id}",
            )],
            [InlineKeyboardButton(
                text="💰 Amount မမှန်",
                callback_data=f"adm:tp:rj:r2:{topup_id}",
            )],
            [InlineKeyboardButton(
                text="🔁 Duplicate",
                callback_data=f"adm:tp:rj:r3:{topup_id}",
            )],
            [InlineKeyboardButton(
                text="✏️ Custom",
                callback_data=f"adm:tp:rj:rc:{topup_id}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"adm:tp:{topup_id}",
            )],
        ]
    )


def topup_reject_confirm_kb(
    topup_id: int, reason_code: str
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ Yes, Reject",
                callback_data=(
                    f"adm:tp:rj:ok:{reason_code}:{topup_id}"
                ),
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"adm:tp:{topup_id}",
            )],
        ]
    )


def topup_adjust_back_kb(
    topup_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"adm:tp:{topup_id}",
            )],
        ]
    )


# ═══ CATEGORIES ═══

def category_list_kb(cats) -> InlineKeyboardMarkup:
    rows = []
    for c in (cats or []):
        icon = "📁" if c.is_active else "⏸️"
        rows.append([InlineKeyboardButton(
            text=f"{icon} {c.name}",
            callback_data=f"acat:{c.id}",
        )])
    rows.append([InlineKeyboardButton(
        text="➕ Category အသစ်",
        callback_data="acat:add",
    )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Panel",
        callback_data="admin:panel",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_confirm_kb(cat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Yes, Delete",
                callback_data=f"acat:del:yes:{cat_id}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"acat:{cat_id}",
            )],
        ]
    )


def category_back_kb(cat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=f"acat:{cat_id}",
            )],
        ]
    )


# ═══ BOOK ADD FLOW ═══

def book_cancel_kb(cat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=f"abk:cancel:{cat_id}",
            )],
        ]
    )


def book_cover_kb(cat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⏭️ Skip",
                callback_data=f"abk:skipcover:{cat_id}",
            )],
            [InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=f"abk:cancel:{cat_id}",
            )],
        ]
    )


def book_status_kb(cat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏳ Ongoing",
                    callback_data=f"abk:status:ongoing:{cat_id}",
                ),
                InlineKeyboardButton(
                    text="✅ Finished",
                    callback_data=f"abk:status:finished:{cat_id}",
                ),
            ],
            [InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=f"abk:cancel:{cat_id}",
            )],
        ]
    )


def book_episode_kb(
    cat_id: int, ep_count: int
) -> InlineKeyboardMarkup:
    rows = []
    if ep_count >= 1:
        rows.append([InlineKeyboardButton(
            text=f"➕ Ep {ep_count + 1} Add",
            callback_data=f"abk:addep:{cat_id}",
        )])
    rows.append([InlineKeyboardButton(
        text="✅ Save & Finish",
        callback_data=f"abk:save:{cat_id}",
    )])
    rows.append([InlineKeyboardButton(
        text="❌ Cancel",
        callback_data=f"abk:cancel:{cat_id}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══ BOOK DETAIL (admin) ═══

def book_detail_admin_kb(
    book_id: int, status: str
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text="➕ Episode Add",
            callback_data=f"abk:addep2:{book_id}",
        )],
        [InlineKeyboardButton(
            text="✏️ Edit",
            callback_data=f"abk:edit:{book_id}",
        )],
    ]

    if status == "ongoing":
        rows.append([InlineKeyboardButton(
            text="✅ Mark Finished",
            callback_data=f"abk:finish:{book_id}",
        )])
    else:
        rows.append([InlineKeyboardButton(
            text="📦 Bulk Price",
            callback_data=f"abk:bulk:{book_id}",
        )])

    rows.append([
        InlineKeyboardButton(
            text="📢 Re-post",
            callback_data=f"abk:repost:{book_id}",
        ),
        InlineKeyboardButton(
            text="🗑️ Delete",
            callback_data=f"abk:del:{book_id}",
        ),
    ])
    rows.append([InlineKeyboardButton(
        text="⬅️ Category",
        callback_data=f"abk:backcat:{book_id}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def book_edit_kb(book_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✏️ Title",
                callback_data=f"abk:edit:title:{book_id}",
            )],
            [InlineKeyboardButton(
                text="✏️ Author",
                callback_data=f"abk:edit:author:{book_id}",
            )],
            [InlineKeyboardButton(
                text="🔄 Cover",
                callback_data=f"abk:edit:cover:{book_id}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Book",
                callback_data=f"abk:view:{book_id}",
            )],
        ]
    )


def book_delete_confirm_kb(
    book_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🗑️ Yes, Delete",
                callback_data=f"abk:del:yes:{book_id}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Cancel",
                callback_data=f"abk:view:{book_id}",
            )],
        ]
    )


# ═══ SETTINGS ═══

def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="💳 Payment Accounts",
                callback_data="set:pay",
            )],
            [InlineKeyboardButton(
                text="💰 Pricing",
                callback_data="set:price",
            )],
            [InlineKeyboardButton(
                text="💰 Topup Config",
                callback_data="set:topup",
            )],
            [InlineKeyboardButton(
                text="☎️ Support Contact",
                callback_data="set:support",
            )],
            [InlineKeyboardButton(
                text="📢 Channels",
                callback_data="set:channels",
            )],
            [InlineKeyboardButton(
                text="🧹 DB Clean",
                callback_data="set:clean",
            )],
            [InlineKeyboardButton(
                text="⬅️ Panel",
                callback_data="admin:panel",
            )],
        ]
    )


def settings_pay_kb(
    has_kpay: bool, has_wave: bool
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"📱 KPay ({'✅' if has_kpay else '❌'})",
                callback_data="set:pay:kpay",
            )],
            [InlineKeyboardButton(
                text=f"🌊 Wave ({'✅' if has_wave else '❌'})",
                callback_data="set:pay:wave",
            )],
            [InlineKeyboardButton(
                text="⬅️ Settings",
                callback_data="set:menu",
            )],
        ]
    )


def settings_pay_edit_kb(method: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✏️ Edit",
                callback_data=f"set:pay:edit:{method}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data="set:pay",
            )],
        ]
    )


def settings_back_kb(
    target: str = "set:menu",
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=target,
            )],
        ]
    )


# ═══ DB CLEAN ═══

def db_clean_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📊 Stats",
                callback_data="clean:stats",
            )],
            [InlineKeyboardButton(
                text="📋 Ledger (180d+)",
                callback_data="clean:audit",
            )],
            [InlineKeyboardButton(
                text="📜 Resolved Topups (30d+)",
                callback_data="clean:topup",
            )],
            [InlineKeyboardButton(
                text="⬅️ Settings",
                callback_data="set:menu",
            )],
        ]
    )


def clean_confirm_kb(
    action: str, target: str
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Yes, Delete",
                callback_data=f"clean:do:{action}:{target}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data="set:clean",
            )],
        ]
    )


def clean_final_kb(
    action: str, target: str
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🔴 Final Confirm — DELETE",
                callback_data=f"clean:final:{action}:{target}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Cancel",
                callback_data="set:clean",
            )],
        ]
    )


# ═══ STATS ═══

def stats_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🔄 Refresh",
                callback_data="stats:show",
            )],
            [InlineKeyboardButton(
                text="🏆 Top Books",
                callback_data="stats:top",
            )],
            [InlineKeyboardButton(
                text="⬅️ Panel",
                callback_data="admin:panel",
            )],
        ]
    )


# ═══ PROMO ═══

def promo_admin_kb(codes) -> InlineKeyboardMarkup:
    rows = []
    for p in codes:
        icon = "✅" if p.is_active else "❌"
        if p.discount_type == "percent":
            val = f"{p.discount_value}%"
        else:
            val = f"{p.discount_value:,} Ks"
        rows.append([InlineKeyboardButton(
            text=f"{icon} {p.code} — {val} (used {p.used_count})",
            callback_data=f"apromo:view:{p.id}",
        )])
    rows.append([InlineKeyboardButton(
        text="➕ Code အသစ်",
        callback_data="apromo:new",
    )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Panel",
        callback_data="admin:panel",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def promo_view_kb(
    promo_id: int, is_active: bool
) -> InlineKeyboardMarkup:
    toggle = "❌ ပိတ်" if is_active else "✅ ဖွင့်"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=toggle,
                callback_data=f"apromo:toggle:{promo_id}",
            )],
            [InlineKeyboardButton(
                text="🗑️ ဖျက်",
                callback_data=f"apromo:del:{promo_id}",
            )],
            [InlineKeyboardButton(
                text="⬅️ List",
                callback_data="apromo:list",
            )],
        ]
    )


def promo_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="💰 Fixed (Ks)",
                callback_data="apromo:type:fixed",
            )],
            [InlineKeyboardButton(
                text="📊 Percent (%)",
                callback_data="apromo:type:percent",
            )],
            [InlineKeyboardButton(
                text="❌ Cancel",
                callback_data="apromo:cancel",
            )],
        ]
    )


def promo_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Save",
                callback_data="apromo:save",
            )],
            [InlineKeyboardButton(
                text="❌ Cancel",
                callback_data="apromo:cancel",
            )],
        ]
    )


def promo_delete_confirm_kb(
    promo_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🗑️ Yes, Delete",
                callback_data=f"apromo:del:yes:{promo_id}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"apromo:view:{promo_id}",
            )],
        ]
    )


# ═══ BOOK REQUESTS ═══

def requests_admin_kb(reqs) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"#{r.id} — {r.title[:35]}",
            callback_data=f"areq:view:{r.id}",
        )]
        for r in reqs
    ]
    rows.append([InlineKeyboardButton(
        text="⬅️ Panel",
        callback_data="admin:panel",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def request_view_kb(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Added (Book ID ထည့်)",
                callback_data=f"areq:added:{req_id}",
            )],
            [InlineKeyboardButton(
                text="❌ Reject (Reason)",
                callback_data=f"areq:rej:{req_id}",
            )],
            [InlineKeyboardButton(
                text="⬅️ List",
                callback_data="areq:list",
            )],
        ]
    )


# ═══ ANALYTICS ═══

def analytics_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📈 Revenue (7d)",
                callback_data="ana:rev7",
            )],
            [InlineKeyboardButton(
                text="📈 Revenue (30d)",
                callback_data="ana:rev30",
            )],
            [InlineKeyboardButton(
                text="👥 User Growth",
                callback_data="ana:growth",
            )],
            [InlineKeyboardButton(
                text="🔻 Funnel (30d)",
                callback_data="ana:funnel",
            )],
            [InlineKeyboardButton(
                text="🏆 Top Books",
                callback_data="ana:books",
            )],
            [InlineKeyboardButton(
                text="📁 Top Categories",
                callback_data="ana:cats",
            )],
            [InlineKeyboardButton(
                text="⬅️ Panel",
                callback_data="admin:panel",
            )],
        ]
    )


# ═══ USERS ═══

def users_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🔍 Search User",
                callback_data="auser:search",
            )],
            [InlineKeyboardButton(
                text="⬅️ Panel",
                callback_data="admin:panel",
            )],
        ]
    )


def user_view_kb(
    user_id: int, is_blocked: bool
) -> InlineKeyboardMarkup:
    toggle = "✅ Unban" if is_blocked else "🚫 Ban"
    toggle_cb = (
        f"auser:unban:{user_id}" if is_blocked
        else f"auser:ban:{user_id}"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="💬 DM ပို့",
                callback_data=f"auser:dm:{user_id}",
            )],
            [
                InlineKeyboardButton(
                    text="➕ Credit",
                    callback_data=f"auser:cr:{user_id}",
                ),
                InlineKeyboardButton(
                    text="➖ Debit",
                    callback_data=f"auser:db:{user_id}",
                ),
            ],
            [InlineKeyboardButton(
                text=toggle,
                callback_data=toggle_cb,
            )],
            [InlineKeyboardButton(
                text="⬅️ Menu",
                callback_data="auser:menu",
            )],
        ]
    )


# ═══ BULK TOOLS ═══

def bulk_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📢 Broadcast (All)",
                callback_data="abulk:broadcast",
            )],
            [InlineKeyboardButton(
                text="📢 Broadcast (Active 7d)",
                callback_data="abulk:bcast_active",
            )],
            [InlineKeyboardButton(
                text="💰 Bulk Credit (Active)",
                callback_data="abulk:credit",
            )],
            [InlineKeyboardButton(
                text="⬅️ Panel",
                callback_data="admin:panel",
            )],
        ]
    )


# ═══ EXPORT ═══

def export_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="👥 Users CSV",
                callback_data="exp:users",
            )],
            [InlineKeyboardButton(
                text="🛒 Purchases (30d)",
                callback_data="exp:purchases",
            )],
            [InlineKeyboardButton(
                text="📜 Ledger (30d)",
                callback_data="exp:ledger",
            )],
            [InlineKeyboardButton(
                text="⬅️ Panel",
                callback_data="admin:panel",
            )],
        ]
    )
