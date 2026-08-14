import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base, Users
from src.db.repository import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_role,
)
from src.db.schemas import UserCreate, UserRoleUpdate
from src.db.session import Database
from src.utils.handle_configs import ConfigManager

cfg_mgr = ConfigManager()
db = Database(db_url=cfg_mgr.settings.database_url)

test_id = "024b1bb4-154a-489e-890f-a2ec953e1b91"
test_email = "manual.user@example.com"


# --- pytest fixtures ---
@pytest.fixture(scope="function")
def db_session():
    """ create an in-memory SQLite database session for each test, ensuring a completely clean state """

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()


    try:
        yield session
    finally:
        session.close()


# --- 1. test case ---
def test_user_create_success(db_session: Session): ...


# --- 2. test case ---
def test_get_user_by_email_success(db_session: Session):
    """ test retrieving an existing user by email """

    manual_user = Users(
            id=test_id,
            email=test_email,
            verified_domain="example.com",
            role="admin",
            trust_score=4.5,
            password="super-secret-password",
            active=True,
        )
    
    db_session.add(manual_user)
    db_session.commit()

    # 1. Act: call the function
    found_user = get_user_by_email(db_session, test_email)

    # 2. assert: check the result
    assert found_user is not None
    assert found_user.id == test_id
    assert found_user.email == test_email


def test_get_user_by_email_not_found(db_session: Session):
    """ Test retrieving a non-existent email returns None. """

    # 1. Act: call the function
    found_user = get_user_by_email(db_session, "nonexistent@example.com")

    # 2. assert: check the result
    assert found_user is None


# --- 3. test case ---
def test_get_user_by_id_success(db_session: Session):
    """ test retrieving an existing user by email"""
    manual_user = Users(
                id=test_id,
                email=test_email,
                verified_domain="example.com",
                role="admin",
                trust_score=4.5,
                password="super-secret-password",
                active=True,
            )
        
    db_session.add(manual_user)
    db_session.commit()

    # 1. Act: call the function
    found_user = get_user_by_id(db_session, test_id)

    # 3. assert: check the result
    assert found_user is not None
    assert found_user.id == test_id
    assert found_user.email == test_email


def test_get_user_by_id_not_found(db_session: Session):
    """ Test retrieving a non-existent id returns None. """

    # 1. Act: call the function
    found_user = get_user_by_id(db_session, "nonexistent-id")

    # 2. assert: check the result
    assert found_user is None


# --- 3. test case ---
def test_update_role_success(db_session: Session):
    """ test updating role of existing  user """
    role = "student"

    # 1. Act call the function
    payload = UserRoleUpdate(id=test_id, role=role)
    updated_user = update_role(db_session, payload)

    # 2. assert: check the result
    assert updated_user is not None
    assert updated_user.id == id
    assert updated_user.role == role


def test_delete_user_by_id(db_session: Session):
    """ test deleting existing user in database """

    # 1. Act: call the function
    is_deleted = test_delete_user_by_id(db_session, test_id)

    # 2. assert: check the result
    is_deleted == True
