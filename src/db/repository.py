

from uuid import uuid4

from sqlalchemy.orm import Session

from src.auth import hash_password
from src.db.models import Users
from src.db.schemas import UserCreate, UserUpdate


def create_user(session: Session, payload: UserCreate) -> Users:
    """ Create a new user using payload """
    user_data = payload.model_dump()

    user_data["id"] = str(uuid4())
    user_data["password"] = hash_password(user_data["password"])

    new_user = Users(**user_data)

    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return new_user
    

def get_user_by_email(session: Session, email: str) -> Users:
    """ Fetch user by email """
    return session.get(Users, email)

def get_user_by_id(session: Session, id: str) -> Users:
    """ Fetch user by email """
    return session.get(Users, id)

def update_role(session: Session, id: str, payload: UserUpdate) -> Users:
    """ Update user """
    user = session.get(Users, id)
    if not user:
        return None

    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(user, key, value)

    session.flush()
    session.refresh(user)
    return user

def delete_user_by_id(session: Session, id: str) -> bool:
    """ delete user from database """
    user = session.get(Users, id)
    if not user:
        return None

    session.delete(user)
    return True
