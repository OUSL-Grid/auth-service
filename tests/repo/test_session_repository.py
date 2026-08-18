from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.exceptions import (
    SessionExpiredError,
    SessionNotFoundError,
    SessionRevokedError,
)
from src.db.models import Base, UserSessions
from src.db.schemas import SessionCreate
from src.db.session_repository import SessionRepository

test_id = "024b1bb4-154a-489e-890f-a2ec953e1b91"
test_email = "manual.user@example.com"
test_user_agent = "example-user-agent"
test_ip_address = "216.144.180.158"
test_refresh_token_hash = "d3b07384d113edec49eaa6238ad5ff00"


def future_expiry(minutes: int = 15) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


def past_expiry(minutes: int = 15) -> datetime:
    return datetime.now(UTC) - timedelta(minutes=minutes)


# --- pytest fixtures ---
@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Async in-memory SQLite session, fresh for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestingSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with TestingSessionLocal() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
def repo(db_session: AsyncSession) -> SessionRepository:
    return SessionRepository(db_session)


# --- 1. create_session ---
@pytest.mark.asyncio
async def test_create_session_success(repo: SessionRepository):
    payload = SessionCreate(
        user_id=test_id,
        refresh_token_hash=test_refresh_token_hash,
        expires_at=future_expiry(),
        user_agent=test_user_agent,
        ip_address=test_ip_address,
    )
    session = await repo.create_session(payload)

    assert session.id is not None
    assert session.user_id == test_id
    assert session.refresh_token_hash == test_refresh_token_hash
    assert session.user_agent == test_user_agent
    assert session.ip_address == test_ip_address
    assert session.revoked_at is None


# --- 2. get_session_by_hash ---
@pytest.mark.asyncio
async def test_get_session_by_hash_success(db_session: AsyncSession, repo: SessionRepository):
    manual_session = UserSessions(
        id="manual-session-id",
        user_id=test_id,
        refresh_token_hash=test_refresh_token_hash,
        expires_at=future_expiry(),
        user_agent=test_user_agent,
        ip_address=test_ip_address,
    )
    db_session.add(manual_session)
    await db_session.commit()

    found_session = await repo.get_session_by_hash(test_refresh_token_hash)

    assert found_session is not None
    assert found_session.user_id == test_id
    assert found_session.refresh_token_hash == test_refresh_token_hash
    assert found_session.user_agent == test_user_agent
    assert found_session.ip_address == test_ip_address


@pytest.mark.asyncio
async def test_get_session_by_hash_not_found(repo: SessionRepository):
    with pytest.raises(SessionNotFoundError):
        await repo.get_session_by_hash(test_refresh_token_hash)


@pytest.mark.asyncio
async def test_get_session_by_hash_expired(db_session: AsyncSession, repo: SessionRepository):
    manual_session = UserSessions(
        id="expired-session-id",
        user_id=test_id,
        refresh_token_hash=test_refresh_token_hash,
        expires_at=past_expiry(),  # already expired
        user_agent=test_user_agent,
        ip_address=test_ip_address,
    )
    db_session.add(manual_session)
    await db_session.commit()

    with pytest.raises(SessionExpiredError):
        await repo.get_session_by_hash(test_refresh_token_hash)


@pytest.mark.asyncio
async def test_get_session_by_hash_revoked(db_session: AsyncSession, repo: SessionRepository):
    manual_session = UserSessions(
        id="revoked-session-id",
        user_id=test_id,
        refresh_token_hash=test_refresh_token_hash,
        expires_at=future_expiry(),
        revoked_at=datetime.now(UTC),  # already revoked
        user_agent=test_user_agent,
        ip_address=test_ip_address,
    )
    db_session.add(manual_session)
    await db_session.commit()

    with pytest.raises(SessionRevokedError):
        await repo.get_session_by_hash(test_refresh_token_hash)


# --- 3. revoke_session ---
@pytest.mark.asyncio
async def test_revoke_session_success(db_session: AsyncSession, repo: SessionRepository):
    manual_session = UserSessions(
        id="session-to-revoke",
        user_id=test_id,
        refresh_token_hash=test_refresh_token_hash,
        expires_at=future_expiry(),
        user_agent=test_user_agent,
        ip_address=test_ip_address,
    )
    db_session.add(manual_session)
    await db_session.commit()

    await repo.revoke_session("session-to-revoke")

    # confirm revocation is visible via the same lookup path used at login
    with pytest.raises(SessionRevokedError):
        await repo.get_session_by_hash(test_refresh_token_hash)


# --- 4. revoke_all_for_user ---
@pytest.mark.asyncio
async def test_revoke_all_for_user_success(db_session: AsyncSession, repo: SessionRepository):
    sessions = [
        UserSessions(
            id=f"session-{i}",
            user_id=test_id,
            refresh_token_hash=f"hash-{i}",
            expires_at=future_expiry(),
            user_agent=test_user_agent,
            ip_address=test_ip_address,
        )
        for i in range(3)
    ]
    db_session.add_all(sessions)
    await db_session.commit()

    revoked_count = await repo.revoke_all_for_user(test_id)

    assert revoked_count == 3
    for i in range(3):
        with pytest.raises(SessionRevokedError):
            await repo.get_session_by_hash(f"hash-{i}")


@pytest.mark.asyncio
async def test_revoke_all_for_user_excludes_already_revoked(
    db_session: AsyncSession, repo: SessionRepository
):
    active_session = UserSessions(
        id="active-session",
        user_id=test_id,
        refresh_token_hash="active-hash",
        expires_at=future_expiry(),
        user_agent=test_user_agent,
        ip_address=test_ip_address,
    )
    already_revoked = UserSessions(
        id="already-revoked-session",
        user_id=test_id,
        refresh_token_hash="already-revoked-hash",
        expires_at=future_expiry(),
        revoked_at=datetime.now(UTC),
        user_agent=test_user_agent,
        ip_address=test_ip_address,
    )
    db_session.add_all([active_session, already_revoked])
    await db_session.commit()

    revoked_count = await repo.revoke_all_for_user(test_id)

    # only the active session should count — already-revoked one isn't re-touched
    assert revoked_count == 1


@pytest.mark.asyncio
async def test_revoke_all_for_user_no_sessions(repo: SessionRepository):
    revoked_count = await repo.revoke_all_for_user("user-with-no-sessions")
    assert revoked_count == 0