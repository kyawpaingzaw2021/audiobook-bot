"""UserCode model — persistent referral code."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class UserCode(Base):
    """One referral code per user."""

    __tablename__ = "user_codes"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), primary_key=True
    )
    code: Mapped[str] = mapped_column(
        String(20), unique=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<UserCode u={self.user_id} {self.code}>"
