"""User model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class User(Base):
    """Telegram bot user."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_user_balance_nonneg"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    tg_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True
    )

    username: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    first_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    balance: Mapped[int] = mapped_column(BigInteger, default=0)
    accepted_terms: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<User tg_id={self.tg_id} balance={self.balance}>"
