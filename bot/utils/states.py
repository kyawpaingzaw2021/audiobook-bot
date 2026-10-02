"""All FSM states (grouped by area)."""
from aiogram.fsm.state import State, StatesGroup


# ═══ USER ═══

class Topup(StatesGroup):
    awaiting_screenshot = State()
    custom = State()


class Search(StatesGroup):
    query = State()


class Rate(StatesGroup):
    comment = State()


class BookReq(StatesGroup):
    title = State()
    author = State()
    note = State()
    confirm = State()


class Buy(StatesGroup):
    promo_code = State()
    batch = State()


# ═══ ADMIN — BOOK ═══

class BookAdd(StatesGroup):
    title = State()
    author = State()
    cover = State()
    status = State()
    ep1 = State()
    episodes = State()


class BookEdit(StatesGroup):
    title = State()
    author = State()
    cover = State()


class BookBulk(StatesGroup):
    price = State()


class AddEp(StatesGroup):
    file = State()


class AdminFinish(StatesGroup):
    bulk_price = State()


class AdminEditPrice(StatesGroup):
    value = State()


# ═══ ADMIN — CATEGORY ═══

class CatAdd(StatesGroup):
    name = State()


class CatRename(StatesGroup):
    name = State()


# ═══ ADMIN — PROMO ═══

class AdminPromo(StatesGroup):
    code = State()
    type = State()
    value = State()
    min_purchase = State()
    max_uses = State()
    confirm = State()


# ═══ ADMIN — TOPUP ═══

class AdminReject(StatesGroup):
    custom = State()


class AdminAdjust(StatesGroup):
    amount = State()


# ═══ ADMIN — REQUEST ═══

class AdminReq(StatesGroup):
    book_id = State()
    reject_reason = State()


# ═══ ADMIN — USER ═══

class AdminUser(StatesGroup):
    search = State()
    dm_text = State()
    adj_amount = State()
    adj_reason = State()


# ═══ ADMIN — BULK ═══

class Bulk(StatesGroup):
    message = State()
    confirm = State()
    credit_amount = State()
    credit_reason = State()
    credit_confirm = State()


# ═══ ADMIN — SETTINGS ═══

class AdminSetting(StatesGroup):
    pay_accounts = State()
