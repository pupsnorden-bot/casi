from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (PrimaryKeyConstraint("user_id", "chat_id", name="pk_user_chat"),)

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, default=500, nullable=False)
    daily_words: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Duel(Base):
    __tablename__ = "duels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    creator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    creator_username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    opponent_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    opponent_username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    creator_outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    opponent_outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bet: Mapped[int] = mapped_column(BigInteger, nullable=False)
    game_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="WAITING", nullable=False)
