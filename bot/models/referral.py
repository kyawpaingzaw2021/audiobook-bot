"""Referral model — tracks referrer to referred relationship."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class Referral(Base):
    """One row per referred user."""

    __tablename__ = "referrals"
    __table_args__ = (
        Index("ix_referral_referrer_paid", "referrer_id", "bonus_paid"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )

    referrer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True
    )
    referred_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), unique=True, index=True
    )

    ref_code: Mapped[str] = mapped_column(String(20), index=True)

    bonus_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    bonus_amount: Mapped[int] = mapped_column(BigInteger, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<Referral {self.ref_code} "
            f"r={self.referrer_id} d={self.referred_id}>"
        )
