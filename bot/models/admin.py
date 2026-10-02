"""Admin model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class Admin(Base):
    """DB-backed admin account."""

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    tg_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True
    )
    username: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    role: Mapped[str] = mapped_column(String(20), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_by: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Admin tg_id={self.tg_id} role={self.role}>"
