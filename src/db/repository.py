from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth import hash_password
from src.db.models import Users
from src.db.schemas import UserCreate, UserRoleUpdate


def create_user(session: Session, payload: UserCreate) -> Users:
    """Create a new user using payload"""
    user_data = payload.model_dump()

    user_data["id"] = str(uuid4())

    new_user = Users(**user_data)

    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return new_user


def get_user_by_email(session: Session, email: str) -> Users:
    """Fetch user by email"""
    return session.execute(
        select(Users).where(Users.email == email)
    ).scalar_one_or_none()


def get_user_by_id(session: Session, id: str) -> Users:
    """Fetch user by email"""
    return session.execute(select(Users).where(Users.id == id)).scalar_one_or_none()


def update_role(session: Session, payload: UserRoleUpdate) -> Users:
    user = session.get(Users, payload.id)
    if not user:
        return None

    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(user, key, value)

    session.commit()
    session.refresh(user)
    return user


def delete_user_by_id(session: Session, id: str) -> bool:
    """delete user from database"""
    user = session.get(Users, id)
    if not user:
        return False
    session.delete(user)
    session.commit()
    return True
