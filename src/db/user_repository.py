from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import UserNotFoundError
from src.db.models import Users as UserModel
from src.db.schemas import UserCreate, UserRoleUpdate


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, payload: UserCreate) -> UserModel:
        """Create a new user using payload"""
        user_data = payload.model_dump()
        user_data["id"] = str(uuid4())

        new_user = UserModel(**user_data)  # <-- was UserCreate(**user_data)

        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)

        return new_user

    async def get_user_by_email(self, email: str) -> UserModel | None:
        """Fetch user by email"""
        result = await self.db.execute(
            select(UserModel).where(UserModel.email == email)  # <-- was UserCreate
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise UserNotFoundError(f"User with email {email} not found")
        return user

    async def get_user_by_id(self, id: str) -> UserModel:
        """Fetch user by id"""
        result = await self.db.execute(  # <-- was missing await
            select(UserModel).where(UserModel.id == id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise UserNotFoundError(f"User with id: {id} not found")
        return user

    async def update_role(self, payload: UserRoleUpdate) -> UserModel:
        await self.db.execute(
            update(UserModel).where(UserModel.id == payload.id).values(role=payload.role)
        )
        await self.db.commit()
        return await self.get_user_by_id(payload.id)  # <-- now actually returns something

    async def delete_user_by_id(self, id: str) -> bool:
        """Delete user from database"""
        result = await self.db.execute(
            delete(UserModel).where(UserModel.id == id)  # <-- was undefined user_id
        )
        await self.db.commit()
        return result.rowcount > 0  # <-- now actually returns bool