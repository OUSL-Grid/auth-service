from datetime import UTC, datetime, timezone
from multiprocessing.pool import INIT
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase): ...


class Users(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    verified_domain: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="student")
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    password: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # --- RELATIONSHIP ---
    # One user can have many sessions. Deleting a user cascades to delete their sessions.
    sessions: Mapped[List["UserSessions"]] = relationship(
        "UserSessions",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"Id: {self.id}, email: {self.email}, create at: {self.created_at}"


class UserSessions(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )
    issued_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(default=None, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- RELATIONSHIP ---
    # Many sessions belong to one user.
    user: Mapped["Users"] = relationship("Users", back_populates="sessions")

    def __repr__(self):
        return f"Id: {self.id}, user id: {self.user_id}, issued at: {self.issued_at}"
