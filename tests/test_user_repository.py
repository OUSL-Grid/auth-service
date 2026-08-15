import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.models import Base, Users
from src.db.schemas import UserCreate, UserRoleUpdate
from src.db.user_repository import UserNotFoundError, UserRepository

test_id = "024b1bb4-154a-489e-890f-a2ec953e1b91"
test_email = "manual.user@example.com"


# --- pytest fixtures ---
@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Async in-memory SQLite session, fresh for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,  # keeps the same connection alive across queries
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestingSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with TestingSessionLocal() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
def repo(db_session: AsyncSession) -> UserRepository:
    return UserRepository(db_session)


# --- 1. create_user ---
@pytest.mark.asyncio
async def test_create_user_success(repo: UserRepository):
    payload = UserCreate(
        email=test_email, verified_domain="example.com",
        role="student", trust_score=3.0, active=True,
    )
    user = await repo.create_user(payload)
    assert user.id is not None
    assert user.email == test_email


# --- 2. get_user_by_email ---
@pytest.mark.asyncio
async def test_get_user_by_email_success(db_session: AsyncSession, repo: UserRepository):
    manual_user = Users(
        id=test_id, email=test_email, verified_domain="example.com",
        role="admin", trust_score=4.5, active=True,
    )
    db_session.add(manual_user)
    await db_session.commit()

    found_user = await repo.get_user_by_email(test_email)

    assert found_user is not None
    assert found_user.id == test_id
    assert found_user.email == test_email


@pytest.mark.asyncio
async def test_get_user_by_email_not_found(repo: UserRepository):
    """Repository raises UserNotFoundError rather than returning None."""
    with pytest.raises(UserNotFoundError):
        await repo.get_user_by_email("nonexistent@example.com")


# --- 3. get_user_by_id ---
@pytest.mark.asyncio
async def test_get_user_by_id_success(db_session: AsyncSession, repo: UserRepository):
    manual_user = Users(
        id=test_id, email=test_email, verified_domain="example.com",
        role="admin", trust_score=4.5, active=True,
    )
    db_session.add(manual_user)
    await db_session.commit()

    found_user = await repo.get_user_by_id(test_id)

    assert found_user is not None
    assert found_user.id == test_id
    assert found_user.email == test_email


@pytest.mark.asyncio
async def test_get_user_by_id_not_found(repo: UserRepository):
    with pytest.raises(UserNotFoundError):
        await repo.get_user_by_id("nonexistent-id")


# --- 4. update_role ---
@pytest.mark.asyncio
async def test_update_role_success(db_session: AsyncSession, repo: UserRepository):
    manual_user = Users(
        id=test_id, email=test_email, verified_domain="example.com",
        role="admin", trust_score=4.5, active=True,
    )
    db_session.add(manual_user)
    await db_session.commit()

    payload = UserRoleUpdate(id=test_id, role="student")
    updated_user = await repo.update_role(payload)

    assert updated_user is not None
    assert updated_user.id == test_id
    assert updated_user.role == "student"


# --- 5. delete_user_by_id ---
@pytest.mark.asyncio
async def test_delete_user_by_id_success(db_session: AsyncSession, repo: UserRepository):
    manual_user = Users(
        id=test_id, email=test_email, verified_domain="example.com",
        role="admin", trust_score=4.5, active=True,
    )
    db_session.add(manual_user)
    await db_session.commit()

    is_deleted = await repo.delete_user_by_id(test_id)
    assert is_deleted is True

    with pytest.raises(UserNotFoundError):
        await repo.get_user_by_id(test_id)


@pytest.mark.asyncio
async def test_delete_user_by_id_not_found(repo: UserRepository):
    """Deleting a nonexistent id should report False, not raise."""
    is_deleted = await repo.delete_user_by_id("nonexistent-id")
    assert is_deleted is False  