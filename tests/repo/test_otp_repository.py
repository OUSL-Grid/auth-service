from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.exceptions import (
    CodeConsumedError,
    CodeExpiredError,
    CodeLockedError,
    CodeNotFoundError,
)
from src.db.models import Base, OTPCode, Users
from src.db.otp_repository import MAX_ATTEMPTS, OTPRepository
from src.db.schemas import OTPCodeCreate

test_user_id = "024b1bb4-154a-489e-890f-a2ec953e1b91"
test_email = "manual.user@example.com"
test_code_hash = "d3b07384d113edec49eaa6238ad5ff00"
test_purpose = "magic_link"


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
def repo(db_session: AsyncSession) -> OTPRepository:
    return OTPRepository(db_session)


@pytest_asyncio.fixture
async def existing_user(db_session: AsyncSession) -> Users:
    user = Users(
        id=test_user_id,
        email=test_email,
        verified_domain="example.com",
        role="student",
        trust_score=1.0,
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


# --- 1. create_code ---
@pytest.mark.asyncio
async def test_create_code_success(repo: OTPRepository, existing_user: Users):
    payload = OTPCodeCreate(
        user_id=existing_user.id,
        code_hash=test_code_hash,
        purpose=test_purpose,
        expires_at=future_expiry(),
    )
    code = await repo.create_code(payload)

    assert code.id is not None
    assert code.user_id == existing_user.id
    assert code.code_hash == test_code_hash
    assert code.purpose == test_purpose
    assert code.attempts == 0
    assert code.consumed_at is None


# --- 2. get_valid_code_by_hash ---
@pytest.mark.asyncio
async def test_get_valid_code_by_hash_success(
    db_session: AsyncSession, repo: OTPRepository, existing_user: Users
):
    manual_code = OTPCode(
        id="valid-code-id",
        user_id=existing_user.id,
        code_hash=test_code_hash,
        purpose=test_purpose,
        expires_at=future_expiry(),
    )
    db_session.add(manual_code)
    await db_session.commit()

    found_code = await repo.get_valid_code_by_hash(test_code_hash)

    assert found_code is not None
    assert found_code.code_hash == test_code_hash


@pytest.mark.asyncio
async def test_get_valid_code_by_hash_not_found(repo: OTPRepository):
    with pytest.raises(CodeNotFoundError):
        await repo.get_valid_code_by_hash(test_code_hash)


@pytest.mark.asyncio
async def test_get_valid_code_by_hash_expired(
    db_session: AsyncSession, repo: OTPRepository, existing_user: Users
):
    manual_code = OTPCode(
        id="expired-code-id",
        user_id=existing_user.id,
        code_hash=test_code_hash,
        purpose=test_purpose,
        expires_at=past_expiry(),
    )
    db_session.add(manual_code)
    await db_session.commit()

    with pytest.raises(CodeExpiredError):
        await repo.get_valid_code_by_hash(test_code_hash)


@pytest.mark.asyncio
async def test_get_valid_code_by_hash_consumed(
    db_session: AsyncSession, repo: OTPRepository, existing_user: Users
):
    manual_code = OTPCode(
        id="consumed-code-id",
        user_id=existing_user.id,
        code_hash=test_code_hash,
        purpose=test_purpose,
        expires_at=future_expiry(),
        consumed_at=datetime.now(UTC),
    )
    db_session.add(manual_code)
    await db_session.commit()

    with pytest.raises(CodeConsumedError):
        await repo.get_valid_code_by_hash(test_code_hash)


@pytest.mark.asyncio
async def test_get_valid_code_by_hash_locked(
    db_session: AsyncSession, repo: OTPRepository, existing_user: Users
):
    manual_code = OTPCode(
        id="locked-code-id",
        user_id=existing_user.id,
        code_hash=test_code_hash,
        purpose=test_purpose,
        expires_at=future_expiry(),
        attempts=MAX_ATTEMPTS,
    )
    db_session.add(manual_code)
    await db_session.commit()

    with pytest.raises(CodeLockedError):
        await repo.get_valid_code_by_hash(test_code_hash)


# --- 3. mark_consumed ---
@pytest.mark.asyncio
async def test_mark_consumed_success(
    db_session: AsyncSession, repo: OTPRepository, existing_user: Users
):
    manual_code = OTPCode(
        id="code-to-consume",
        user_id=existing_user.id,
        code_hash=test_code_hash,
        purpose=test_purpose,
        expires_at=future_expiry(),
    )
    db_session.add(manual_code)
    await db_session.commit()

    await repo.mark_consumed("code-to-consume")

    with pytest.raises(CodeConsumedError):
        await repo.get_valid_code_by_hash(test_code_hash)


# --- 4. increment_attempts ---
@pytest.mark.asyncio
async def test_increment_attempts_success(
    db_session: AsyncSession, repo: OTPRepository, existing_user: Users
):
    manual_code = OTPCode(
        id="code-to-increment",
        user_id=existing_user.id,
        code_hash=test_code_hash,
        purpose=test_purpose,
        expires_at=future_expiry(),
    )
    db_session.add(manual_code)
    await db_session.commit()

    new_count = await repo.increment_attempts("code-to-increment")
    assert new_count == 1

    new_count = await repo.increment_attempts("code-to-increment")
    assert new_count == 2


@pytest.mark.asyncio
async def test_increment_attempts_locks_after_max(
    db_session: AsyncSession, repo: OTPRepository, existing_user: Users
):
    """After MAX_ATTEMPTS failed tries, subsequent lookups should raise CodeLockedError."""
    manual_code = OTPCode(
        id="code-to-lock",
        user_id=existing_user.id,
        code_hash=test_code_hash,
        purpose=test_purpose,
        expires_at=future_expiry(),
    )
    db_session.add(manual_code)
    await db_session.commit()

    for _ in range(MAX_ATTEMPTS):
        await repo.increment_attempts("code-to-lock")

    with pytest.raises(CodeLockedError):
        await repo.get_valid_code_by_hash(test_code_hash)


@pytest.mark.asyncio
async def test_increment_attempts_not_found(repo: OTPRepository):
    with pytest.raises(CodeNotFoundError):
        await repo.increment_attempts("nonexistent-code-id")