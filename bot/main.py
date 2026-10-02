"""Bot entry point — init, middlewares, routers, scheduler."""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import config
from bot.services.db import SessionLocal, close_db, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


if sys.platform != "win32":
    try:
        import uvloop

        uvloop.install()
        logger.info("uvloop installed")
    except ImportError:
        pass


def _validate_config() -> None:
    """Check required config keys."""
    errors: list[str] = []

    if not config.BOT_TOKEN or ":" not in config.BOT_TOKEN:
        errors.append("BOT_TOKEN")
    if config.ADMIN_ID == 0:
        errors.append("ADMIN_ID")
    if config.STORAGE_CHAT_ID == 0:
        errors.append("STORAGE_CHAT_ID")
    if config.NOTICE_CHAT_ID == 0:
        errors.append("NOTICE_CHAT_ID")
    if not config.DB_PASSWORD:
        errors.append("DB_PASSWORD")

    if errors:
        msg = "Missing config: " + ", ".join(errors)
        logger.error(msg)
        raise SystemExit(msg)


async def main() -> None:
    logger.info("Bot starting...")

    _validate_config()

    await init_db()

    from bot.services.settings_service import seed_defaults

    async with SessionLocal() as session:
        await seed_defaults(session)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    from bot.middlewares.errors import (
        ErrorMiddleware,
        error_handler,
    )
    from bot.middlewares.rate_limit import RateLimitMiddleware

    err_mw = ErrorMiddleware()
    rl_msg = RateLimitMiddleware(max_events=8, window=3)
    rl_cb = RateLimitMiddleware(max_events=10, window=3)

    dp.message.middleware(err_mw)
    dp.callback_query.middleware(err_mw)
    dp.message.middleware(rl_msg)
    dp.callback_query.middleware(rl_cb)

    dp.errors.register(error_handler)

    from bot.handlers.user import cancel as user_cancel

    dp.include_router(user_cancel.router)

    from bot.handlers.admin import analytics as admin_analytics
    from bot.handlers.admin import book as admin_book
    from bot.handlers.admin import bulk as admin_bulk
    from bot.handlers.admin import category as admin_category
    from bot.handlers.admin import db_clean as admin_clean
    from bot.handlers.admin import episode as admin_episode
    from bot.handlers.admin import export as admin_export
    from bot.handlers.admin import finish as admin_finish
    from bot.handlers.admin import panel as admin_panel
    from bot.handlers.admin import promo as admin_promo
    from bot.handlers.admin import requests as admin_requests
    from bot.handlers.admin import settings as admin_settings
    from bot.handlers.admin import stats as admin_stats
    from bot.handlers.admin import topup as admin_topup
    from bot.handlers.admin import users as admin_users

    dp.include_router(admin_panel.router)
    dp.include_router(admin_stats.router)
    dp.include_router(admin_settings.router)
    dp.include_router(admin_clean.router)
    dp.include_router(admin_category.router)
    dp.include_router(admin_book.router)
    dp.include_router(admin_episode.router)
    dp.include_router(admin_finish.router)
    dp.include_router(admin_topup.router)
    dp.include_router(admin_promo.router)
    dp.include_router(admin_requests.router)
    dp.include_router(admin_analytics.router)
    dp.include_router(admin_users.router)
    dp.include_router(admin_bulk.router)
    dp.include_router(admin_export.router)

    from bot.handlers.user import books as user_books
    from bot.handlers.user import buy as user_buy
    from bot.handlers.user import daily as user_daily
    from bot.handlers.user import leaderboard as user_leaderboard
    from bot.handlers.user import library as user_library
    from bot.handlers.user import menu as user_menu
    from bot.handlers.user import promo as user_promo
    from bot.handlers.user import rating as user_rating
    from bot.handlers.user import referral as user_referral
    from bot.handlers.user import request as user_request
    from bot.handlers.user import search as user_search
    from bot.handlers.user import start as user_start
    from bot.handlers.user import support as user_support
    from bot.handlers.user import topup as user_topup
    from bot.handlers.user import wishlist as user_wishlist

    dp.include_router(user_start.router)
    dp.include_router(user_menu.router)
    dp.include_router(user_referral.router)
    dp.include_router(user_promo.router)
    dp.include_router(user_wishlist.router)
    dp.include_router(user_search.router)
    dp.include_router(user_rating.router)
    dp.include_router(user_request.router)
    dp.include_router(user_leaderboard.router)
    dp.include_router(user_books.router)
    dp.include_router(user_buy.router)
    dp.include_router(user_library.router)
    dp.include_router(user_topup.router)
    dp.include_router(user_support.router)
    dp.include_router(user_daily.router)

    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    logger.info(f"Bot: @{me.username} (ID: {me.id})")
    logger.info(f"Admin: {config.ADMIN_ID}")
    logger.info(f"Storage: {config.STORAGE_CHAT_ID}")
    logger.info(f"Notice: {config.NOTICE_CHAT_ID}")

    from bot.scheduler import setup_scheduler

    scheduler = setup_scheduler(bot)
    scheduler.start()

    try:
        logger.info("Polling started...")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await close_db()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
