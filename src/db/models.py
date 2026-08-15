
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    ...


class Users(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    verified_domain: Mapped[str]
    role: Mapped[str] = mapped_column(default="student")
    trust_score: Mapped[float] = mapped_column(default=1.0)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # --- RELATIONSHIPS ---
    sessions: Mapped[list["UserSessions"]] = relationship(
        "UserSessions",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    oauth_identities: Mapped[list["OAuthIdentity"]] = relationship(
        "OAuthIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    otp_codes: Mapped[list["OTPCode"]] = relationship(
        "OTPCode",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Users id={self.id} email={self.email}>"


class UserSessions(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(Text, unique=True)
    issued_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    user_agent: Mapped[str | None]
    ip_address: Mapped[str | None]

    # --- RELATIONSHIP ---
    user: Mapped["Users"] = relationship("Users", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<UserSessions id={self.id} user_id={self.user_id}>"


class OAuthIdentity(Base):
    __tablename__ = "oauth_identities"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str]
    provider_user_id: Mapped[str]
    access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC)
    )

    # --- RELATIONSHIP ---
    user: Mapped["Users"] = relationship(
        "Users", back_populates="oauth_identities"
    )

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_user"),
    )

    def __repr__(self) -> str:
        return f"<OAuthIdentity id={self.id} provider={self.provider}>"

class OTPCode(Base):
    __tablename__ = "otp_codes"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. "magic_link", "otp"
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(default=None, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    user: Mapped["Users"] = relationship("Users", back_populates="otp_codes")

    def __repr__(self):
        return f"Id: {self.id}, user_id: {self.user_id}, purpose: {self.purpose}"
