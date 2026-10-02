"""Config from environment variables."""
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _int(key: str, default: int = 0) -> int:
    """Safe int from env."""
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
    ADMIN_ID: int = _int("ADMIN_ID", 0)
    STORAGE_CHAT_ID: int = _int("STORAGE_CHAT_ID", 0)
    NOTICE_CHAT_ID: int = _int("NOTICE_CHAT_ID", 0)

    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost").strip()
    DB_PORT: str = os.getenv("DB_PORT", "5432").strip()
    DB_NAME: str = os.getenv("DB_NAME", "audiobook").strip()
    DB_USER: str = os.getenv("DB_USER", "bot_user").strip()
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # App
    TZ: str = os.getenv("TZ", "Asia/Yangon").strip()
    BACKUP_DIR: str = os.getenv(
        "BACKUP_DIR", "/opt/audiobook-bot/data/backups"
    ).strip()
    BACKUP_RETENTION_DAYS: int = _int("BACKUP_RETENTION_DAYS", 7)

    @property
    def db_url(self) -> str:
        """Async postgres URL."""
        user = quote_plus(self.DB_USER)
        pwd = quote_plus(self.DB_PASSWORD)
        return (
            f"postgresql+asyncpg://{user}:{pwd}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


config = Config()
