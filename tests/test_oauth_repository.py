from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.exceptions import OAuthIdentityAlreadyLinkedError, UserNotFoundError
from src.db.models import Base, OAuthIdentity, Users
from src.db.oauth_repository import OAuthRepository
from src.db.schemas import OAuthIdentityCreate

test_user_id = "024b1bb4-154a-489e-890f-a2ec953e1b91"
test_email = "manual.user@example.com"
test_provider = "google"
test_provider_user_id = "108234567890123456789"
test_access_token_enc = "encrypted-token-blob"


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
def repo(db_session: AsyncSession) -> OAuthRepository:
    return OAuthRepository(db_session)


@pytest_asyncio.fixture
async def existing_user(db_session: AsyncSession) -> Users:
    """Seed a user that OAuth identities can be linked to."""
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


# --- 1. link_oauth_identity ---
@pytest.mark.asyncio
async def test_link_oauth_identity_success(repo: OAuthRepository, existing_user: Users):
    payload = OAuthIdentityCreate(
        user_id=existing_user.id,
        provider=test_provider,
        provider_user_id=test_provider_user_id,
        access_token_enc=test_access_token_enc,
    )
    identity = await repo.link_oauth_identity(payload)

    assert identity.id is not None
    assert identity.user_id == existing_user.id
    assert identity.provider == test_provider
    assert identity.provider_user_id == test_provider_user_id
    assert identity.access_token_enc == test_access_token_enc


@pytest.mark.asyncio
async def test_link_oauth_identity_duplicate_provider_account_rejected(
    repo: OAuthRepository, existing_user: Users
):
    """Same (provider, provider_user_id) can't be linked twice, even to the same user."""
    payload = OAuthIdentityCreate(
        user_id=existing_user.id,
        provider=test_provider,
        provider_user_id=test_provider_user_id,
    )
    await repo.link_oauth_identity(payload)

    with pytest.raises(OAuthIdentityAlreadyLinkedError):
        await repo.link_oauth_identity(payload)


@pytest.mark.asyncio
async def test_link_oauth_identity_same_google_account_different_user_rejected(
    db_session: AsyncSession, repo: OAuthRepository, existing_user: Users
):
    """A Google account already linked to user A can't also be linked to user B."""
    other_user = Users(
        id="a-different-user-id",
        email="other.user@example.com",
        verified_domain="example.com",
        role="student",
        trust_score=1.0,
        active=True,
    )
    db_session.add(other_user)
    await db_session.commit()

    await repo.link_oauth_identity(
        OAuthIdentityCreate(
            user_id=existing_user.id,
            provider=test_provider,
            provider_user_id=test_provider_user_id,
        )
    )

    with pytest.raises(OAuthIdentityAlreadyLinkedError):
        await repo.link_oauth_identity(
            OAuthIdentityCreate(
                user_id=other_user.id,
                provider=test_provider,
                provider_user_id=test_provider_user_id,  # same Google account
            )
        )


@pytest.mark.asyncio
async def test_link_oauth_identity_same_user_multiple_providers_allowed(
    repo: OAuthRepository, existing_user: Users
):
    """One user can link both Google and another provider without conflict."""
    google_identity = await repo.link_oauth_identity(
        OAuthIdentityCreate(
            user_id=existing_user.id,
            provider="google",
            provider_user_id=test_provider_user_id,
        )
    )
    other_identity = await repo.link_oauth_identity(
        OAuthIdentityCreate(
            user_id=existing_user.id,
            provider="microsoft",
            provider_user_id="some-other-provider-id",
        )
    )

    assert google_identity.user_id == other_identity.user_id
    assert google_identity.provider != other_identity.provider


# --- 2. get_user_by_provider_id ---
@pytest.mark.asyncio
async def test_get_user_by_provider_id_success(repo: OAuthRepository, existing_user: Users):
    await repo.link_oauth_identity(
        OAuthIdentityCreate(
            user_id=existing_user.id,
            provider=test_provider,
            provider_user_id=test_provider_user_id,
        )
    )

    found_user = await repo.get_user_by_provider_id(test_provider, test_provider_user_id)

    assert found_user is not None
    assert found_user.id == existing_user.id
    assert found_user.email == existing_user.email


@pytest.mark.asyncio
async def test_get_user_by_provider_id_not_found(repo: OAuthRepository):
    with pytest.raises(UserNotFoundError):
        await repo.get_user_by_provider_id(test_provider, "unlinked-provider-id")


@pytest.mark.asyncio
async def test_get_user_by_provider_id_wrong_provider_not_found(
    repo: OAuthRepository, existing_user: Users
):
    """Same provider_user_id under a different provider name shouldn't match."""
    await repo.link_oauth_identity(
        OAuthIdentityCreate(
            user_id=existing_user.id,
            provider="google",
            provider_user_id=test_provider_user_id,
        )
    )

    with pytest.raises(UserNotFoundError):
        await repo.get_user_by_provider_id("microsoft", test_provider_user_id)