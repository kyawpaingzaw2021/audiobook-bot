"""Category service — CRUD with deterministic slug."""
import hashlib
import logging
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.category import Category

logger = logging.getLogger(__name__)


def _make_slug(name: str) -> str:
    """Deterministic slug. MD5 fallback for non-latin."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if slug:
        return slug
    h = hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    return f"cat-{h}"


async def list_categories(
    session: AsyncSession, active_only: bool = True
) -> list[Category]:
    """List categories ordered by display_order + name."""
    stmt = select(Category).order_by(
        Category.display_order, Category.name
    )
    if active_only:
        stmt = stmt.where(Category.is_active == True)  # noqa: E712

    r = await session.execute(stmt)
    return list(r.scalars().all())


async def get_category(
    session: AsyncSession, cat_id: int
) -> Category | None:
    """Fetch category by ID."""
    r = await session.execute(
        select(Category).where(Category.id == cat_id)
    )
    return r.scalar_one_or_none()


async def get_by_slug(
    session: AsyncSession, slug: str
) -> Category | None:
    """Fetch category by slug."""
    r = await session.execute(
        select(Category).where(Category.slug == slug)
    )
    return r.scalar_one_or_none()


async def create_category(
    session: AsyncSession, name: str
) -> Category:
    """Create a category. Race-safe."""
    name = name.strip()[:100]
    if not name:
        raise ValueError("Empty name")

    r = await session.execute(
        select(Category).where(Category.name == name)
    )
    if r.scalar_one_or_none() is not None:
        raise ValueError(f"Category '{name}' already exists")

    base_slug = _make_slug(name)
    slug = base_slug
    i = 1
    while True:
        r = await session.execute(
            select(Category).where(Category.slug == slug)
        )
        if r.scalar_one_or_none() is None:
            break
        slug = f"{base_slug}-{i}"
        i += 1

    cat = Category(name=name, slug=slug)
    session.add(cat)

    try:
        await session.commit()
        await session.refresh(cat)
        logger.info(f"Category created: {cat.name} (id={cat.id})")
        return cat
    except IntegrityError:
        await session.rollback()
        r = await session.execute(
            select(Category).where(Category.name == name)
        )
        existing = r.scalar_one_or_none()
        if existing is not None:
            return existing
        raise


async def rename_category(
    session: AsyncSession, cat_id: int, new_name: str
) -> Category | None:
    """Rename category (slug stays)."""
    cat = await get_category(session, cat_id)
    if cat is None:
        return None

    new_name = new_name.strip()[:100]
    if not new_name:
        raise ValueError("Empty name")

    cat.name = new_name
    await session.commit()
    await session.refresh(cat)
    return cat


async def toggle_active(
    session: AsyncSession, cat_id: int
) -> Category | None:
    """Toggle is_active (pause/resume)."""
    cat = await get_category(session, cat_id)
    if cat is None:
        return None

    cat.is_active = not cat.is_active
    await session.commit()
    await session.refresh(cat)
    return cat
