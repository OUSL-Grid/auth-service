

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    SessionExpiredError,
    SessionNotFoundError,
    SessionRevokedError,
)
from src.db.models import UserSessions as SessionModel
from src.db.schemas import SessionCreate


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, payload: SessionCreate) -> SessionModel:
        session = SessionModel(
            id=str(uuid4()),
            user_id=payload.user_id,
            refresh_token_hash=payload.refresh_token_hash,
            expires_at=payload.expires_at,
            user_agent=payload.user_agent,
            ip_address=payload.ip_address,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_session_by_hash(self, refresh_token_hash: str) -> SessionModel:

        result = await self.db.execute(
            select(SessionModel).where(
                SessionModel.refresh_token_hash == refresh_token_hash
            )
        )
        session = result.scalar_one_or_none()

        if session is None:
            raise SessionNotFoundError("Refresh token not recognized")
        if session.revoked_at is not None:
            raise SessionRevokedError("Refresh token has been revoked")
        if session.expires_at < datetime.now(UTC):
            raise SessionExpiredError("Refresh token has expired")

        return session

    async def revoke_session(self, session_id: str) -> None:
        await self.db.execute(
            update(SessionModel)
            .where(SessionModel.id == session_id)
            .values(revoked_at=datetime.now(UTC))
        )
        await self.db.commit()


    async def revoke_all_for_user(self, user_id: str) -> int:
        result = await self.db.execute(
            update(SessionModel)
            .where(SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self.db.commit()
        return result.rowcount
        










