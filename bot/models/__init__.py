"""Models — import all so Base.metadata registers everything."""
from bot.models.base import Base
from bot.models.user import User
from bot.models.admin import Admin
from bot.models.category import Category
from bot.models.book import Book, BookFile
from bot.models.purchase import Purchase
from bot.models.ledger import Ledger
from bot.models.topup import TopupRequest
from bot.models.setting import Setting
from bot.models.checkin import DailyCheckin
from bot.models.user_code import UserCode
from bot.models.referral import Referral
from bot.models.promo import PromoCode, PromoRedemption
from bot.models.wishlist import Wishlist
from bot.models.rating import Rating
from bot.models.book_request import BookRequest

__all__ = [
    "Base",
    "User",
    "Admin",
    "Category",
    "Book",
    "BookFile",
    "Purchase",
    "Ledger",
    "TopupRequest",
    "Setting",
    "DailyCheckin",
    "UserCode",
    "Referral",
    "PromoCode",
    "PromoRedemption",
    "Wishlist",
    "Rating",
    "BookRequest",
]
