"""PromoCode + PromoRedemption models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class PromoCode(Base):
    """Discount promo code."""

    __tablename__ = "promo_codes"
    __table_args__ = (
        Index("ix_promo_active_expires", "is_active", "expires_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    code: Mapped[str] = mapped_column(
        String(30), unique=True, index=True
    )

    discount_type: Mapped[str] = mapped_column(
        String(15), default="fixed"
    )
    discount_value: Mapped[int] = mapped_column(BigInteger)

    min_purchase: Mapped[int] = mapped_column(BigInteger, default=0)
    max_uses: Mapped[int] = mapped_column(Integer, default=0)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    per_user_limit: Mapped[int] = mapped_column(Integer, default=1)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Promo {self.code} used={self.used_count}>"


class PromoRedemption(Base):
    """Tracks each promo redemption."""

    __tablename__ = "promo_redemptions"
    __table_args__ = (
        UniqueConstraint(
            "promo_id", "user_id", "reference",
            name="uq_promo_user_ref",
        ),
        Index("ix_redemption_promo_user", "promo_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    promo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("promo_codes.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True
    )

    discount_amount: Mapped[int] = mapped_column(BigInteger)
    reference: Mapped[str] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Redemption promo={self.promo_id} u={self.user_id}>"
