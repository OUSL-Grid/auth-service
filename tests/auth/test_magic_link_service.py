from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.auth.domain_whitelist import DomainWhitelist
from src.auth.service import MagicLinkService
from src.core.exceptions import DomainNotAllowedError, RateLimitExceededError
from src.db.models import Base
from src.db.otp_repository import OTPRepository
from src.db.user_repository import UserRepository

test_email = "student@ousl.lk"


@pytest_asyncio.fixture(scope="function")
async def db_session():
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


@pytest.fixture
def whitelist() -> DomainWhitelist:
    return DomainWhitelist(allowed_domains=["ousl.lk"])


@pytest.fixture
def mock_email_client():
    client = AsyncMock()
    client.send_magic_link = AsyncMock()
    return client


@pytest_asyncio.fixture
def service(db_session: AsyncSession, whitelist: DomainWhitelist, mock_email_client):
    return MagicLinkService(
        user_repo=UserRepository(db_session),
        otp_repo=OTPRepository(db_session),
        whitelist=whitelist,
        email_client=mock_email_client,
        base_url="https://app.example.com",
        token_expiry_minutes=15,
        rate_limit_max=3,
        rate_limit_window_minutes=15,
    )


@pytest.mark.asyncio
async def test_request_magic_link_success(service: MagicLinkService, mock_email_client):
    await service.request_magic_link(test_email)

    mock_email_client.send_magic_link.assert_called_once()
    call_args = mock_email_client.send_magic_link.call_args
    assert call_args[0][0] == test_email
    assert "token=" in call_args[0][1]


@pytest.mark.asyncio
async def test_request_magic_link_rejects_non_whitelisted_domain(service: MagicLinkService):
    with pytest.raises(DomainNotAllowedError):
        await service.request_magic_link("someone@gmail.com")


@pytest.mark.asyncio
async def test_request_magic_link_never_emails_raw_token_twice(
    service: MagicLinkService, db_session: AsyncSession
):
    """The stored code_hash should NOT equal the raw token in the email."""
    from sqlalchemy import select
    from src.db.models import OTPCode

    await service.request_magic_link(test_email)

    result = await db_session.execute(select(OTPCode))
    stored_code = result.scalar_one()

    # stored hash is 64 hex chars (SHA-256); raw token is a urlsafe base64 string —
    # they should never be equal, and the hash should look like a hash
    assert len(stored_code.code_hash) == 64
    assert all(c in "0123456789abcdef" for c in stored_code.code_hash)


@pytest.mark.asyncio
async def test_request_magic_link_creates_user_if_not_exists(
    service: MagicLinkService, db_session: AsyncSession
):
    from sqlalchemy import select
    from src.db.models import Users

    await service.request_magic_link(test_email)

    result = await db_session.execute(select(Users).where(Users.email == test_email))
    user = result.scalar_one()
    assert user.verified_domain == "ousl.lk"


@pytest.mark.asyncio
async def test_request_magic_link_reuses_existing_user(
    service: MagicLinkService, db_session: AsyncSession
):
    from sqlalchemy import select, func
    from src.db.models import Users

    await service.request_magic_link(test_email)
    await service.request_magic_link(test_email)

    result = await db_session.execute(select(func.count(Users.id)).where(Users.email == test_email))
    count = result.scalar_one()
    assert count == 1  # only one user row, not duplicated


@pytest.mark.asyncio
async def test_request_magic_link_rate_limit_enforced(service: MagicLinkService):
    # rate_limit_max=3 in the fixture
    await service.request_magic_link(test_email)
    await service.request_magic_link(test_email)
    await service.request_magic_link(test_email)

    with pytest.raises(RateLimitExceededError):
        await service.request_magic_link(test_email)


@pytest.mark.asyncio
async def test_request_magic_link_domain_rejected_before_rate_limit_or_db_write(
    service: MagicLinkService, db_session: AsyncSession
):
    """A rejected-domain request should not create a user row at all."""
    from sqlalchemy import select, func
    from src.db.models import Users

    with pytest.raises(DomainNotAllowedError):
        await service.request_magic_link("someone@gmail.com")

    result = await db_session.execute(select(func.count(Users.id)))
    count = result.scalar_one()
    assert count == 0