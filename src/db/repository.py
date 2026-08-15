from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Users as UserModel
from src.db.schemas import UserCreate, UserRoleUpdate
from sqlalchemy.ext.asyncio import AsyncSession

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, payload: UserCreate) -> UserModel:
        """Create a new user using payload"""
        user_data = payload.model_dump()

        user_data["id"] = str(uuid4())

        new_user = UserModel(**user_data)

        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)

        return new_user


    def get_user_by_email(self, email: str) -> UserModel:
        """Fetch user by email"""
        return self.db.execute(
            select(UserCreate).where(UserCreate.email == email)
        ).scalar_one_or_none()


    def get_user_by_id(self, id: str) -> UserModel:
        """Fetch user by email"""
        return self.db.execute(select(UserModel).where(UserModel.id == id)).scalar_one_or_none()


    def update_role(session: Session, payload: UserRoleUpdate) -> UserModel:
        user = session.get(UserModel, payload.id)
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
        user = session.get(UserModel, id)
        if not user:
            return False
        session.delete(user)
        session.commit()
        return True
