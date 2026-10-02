"""DailyCheckin model."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class DailyCheckin(Base):
    """One row per user per day."""

    __tablename__ = "daily_checkins"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "checkin_date", name="uq_user_day"
        ),
        Index("ix_checkin_date", "checkin_date"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True
    )
    checkin_date: Mapped[date] = mapped_column(Date)

    reward: Mapped[int] = mapped_column(Integer)
    streak_count: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<Checkin u={self.user_id} d={self.checkin_date} "
            f"streak={self.streak_count}>"
        )
