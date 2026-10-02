"""Settings service — key/value config with defaults."""
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.setting import Setting

logger = logging.getLogger(__name__)


DEFAULTS: dict[str, str] = {
    "topup_presets": "1000,3000,5000,10000",
    "topup_min": "1000",
    "topup_max": "100000",
    "topup_expire_hours": "24",
    "default_episode_price": "500",
    "kpay_accounts": "09-000-000-000|Your Name",
    "wave_accounts": "",
    "support_telegram": "@your_admin",
    "support_phone": "09-000-000-000",
    "support_hours": "9 AM - 9 PM",
    "support_email": "",
    "daily_reward": "5",
    "first_time_bonus": "100",
    "referral_bonus": "200",
    "reengage_days": "7",
}


async def get_setting(
    session: AsyncSession,
    key: str,
    default: str | None = None,
) -> str:
    """Get setting value. Falls back to DEFAULTS then default."""
    r = await session.execute(
        select(Setting).where(Setting.key == key)
    )
    s = r.scalar_one_or_none()
    if s is not None:
        return s.value
    if default is not None:
        return default
    return DEFAULTS.get(key, "")


async def get_int_setting(
    session: AsyncSession, key: str, default: int = 0
) -> int:
    """Get setting as int."""
    raw = await get_setting(session, key, str(default))
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


async def set_setting(
    session: AsyncSession, key: str, value: str
) -> None:
    """Set setting (insert or update)."""
    r = await session.execute(
        select(Setting).where(Setting.key == key)
    )
    s = r.scalar_one_or_none()

    if s is not None:
        s.value = value
    else:
        session.add(Setting(key=key, value=value))

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        r = await session.execute(
            select(Setting).where(Setting.key == key)
        )
        s = r.scalar_one_or_none()
        if s is not None:
            s.value = value
            await session.commit()


async def get_topup_presets(
    session: AsyncSession,
) -> list[int]:
    """Parse topup presets from setting."""
    raw = await get_setting(session, "topup_presets")
    out: list[int] = []
    for x in raw.split(","):
        x = x.strip()
        if not x:
            continue
        try:
            out.append(int(x))
        except ValueError:
            continue
    return out or [1000, 3000, 5000, 10000]


async def get_payment_accounts(
    session: AsyncSession, method: str
) -> list[str]:
    """Returns list of 'number|name' strings."""
    key = f"{method}_accounts"
    raw = await get_setting(session, key)
    return [x.strip() for x in raw.split(";") if x.strip()]


async def get_topup_expire_hours(
    session: AsyncSession,
) -> int:
    """Topup expire window in hours."""
    return await get_int_setting(
        session, "topup_expire_hours", 24
    )


async def seed_defaults(session: AsyncSession) -> None:
    """Insert missing default settings (1 query)."""
    keys = list(DEFAULTS.keys())
    r = await session.execute(
        select(Setting.key).where(Setting.key.in_(keys))
    )
    existing = {row[0] for row in r.all()}

    added = 0
    for key, value in DEFAULTS.items():
        if key in existing:
            continue
        session.add(Setting(key=key, value=value))
        added += 1

    if added:
        await session.commit()
        logger.info(f"Seeded {added} default settings.")
