from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    CodeConsumedError,
    CodeExpiredError,
    CodeLockedError,
    CodeNotFoundError,
)
from src.db.models import OTPCode as OTPCodeModel
from src.db.schemas import OTPCodeCreate

MAX_ATTEMPTS = 5


class OTPRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_code(self, payload: OTPCodeCreate) -> OTPCodeModel:
        """Create a new OTP/magic-link code record. Caller has already
        hashed the raw code before building the payload."""
        code = OTPCodeModel(
            id=str(uuid4()),
            user_id=payload.user_id,
            code_hash=payload.code_hash,
            purpose=payload.purpose,
            expires_at=payload.expires_at,
        )
        self.db.add(code)
        await self.db.commit()
        await self.db.refresh(code)
        return code

    async def get_valid_code_by_hash(self, code_hash: str) -> OTPCodeModel:
        """
        Look up a code by its hash and validate it's still usable.
        Raises typed exceptions for each failure mode so the service layer
        can map them to distinct, user-facing error messages.
        """
        result = await self.db.execute(
            select(OTPCodeModel).where(OTPCodeModel.code_hash == code_hash)
        )
        code = result.scalar_one_or_none()

        if code is None:
            raise CodeNotFoundError("Code not recognized")
        if code.consumed_at is not None:
            raise CodeConsumedError("Code has already been used")
        if code.attempts >= MAX_ATTEMPTS:
            raise CodeLockedError("Too many failed attempts, code locked")
        if code.expires_at < datetime.now(UTC):
            raise CodeExpiredError("Code has expired")

        return code

    async def mark_consumed(self, code_id: str) -> None:
        await self.db.execute(
            update(OTPCodeModel)
            .where(OTPCodeModel.id == code_id)
            .values(consumed_at=datetime.now(UTC))
        )
        await self.db.commit()

    async def increment_attempts(self, code_id: str) -> int:
        """
        Called on each failed verification attempt (e.g. wrong OTP digits
        typed in). Returns the new attempt count so the caller can decide
        whether to tell the user they're close to being locked out.
        """
        result = await self.db.execute(
            select(OTPCodeModel).where(OTPCodeModel.id == code_id)
        )
        code = result.scalar_one_or_none()
        if code is None:
            raise CodeNotFoundError(f"Code {code_id} not found")

        new_attempts = code.attempts + 1
        await self.db.execute(
            update(OTPCodeModel)
            .where(OTPCodeModel.id == code_id)
            .values(attempts=new_attempts)
        )
        await self.db.commit()
        return new_attempts

    async def count_recent_codes_for_user(
            self, user_id: str, purpose: str, window_minutes: int = 15
    ) -> int:
        """
        Counts codes issued to this user for this purpose within the window —
        used for rate limiting. Doesn't care if they were consumed/expired,
        since the point is to cap *issuance* rate, not usage.
        """

        cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
        result = await self.db.execute(
            select(func.count(OTPCodeModel.id)).where(
                OTPCodeModel.user_id == user_id,
                OTPCodeModel.purpose == purpose,
                OTPCodeModel.created_at >= cutoff,
            )
        )
        return result.scalar_one()