from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import OAuthIdentityAlreadyLinkedError, UserNotFoundError
from src.db.models import OAuthIdentity as OAuthIdentityModel
from src.db.models import Users as UserModel
from src.db.schemas import OAuthIdentityCreate


class OAuthRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def link_oauth_identity(self, payload: OAuthIdentityCreate) -> OAuthIdentityModel:
        """
        Link an OAuth provider account to an existing user.
        Raises if this provider account is already linked (to this user or another).
        """
        identity = OAuthIdentityModel(
            id=str(uuid4()),
            user_id=payload.user_id,
            provider=payload.provider,
            provider_user_id=payload.provider_user_id,
            access_token_enc=payload.access_token_enc,
        )
        self.db.add(identity)
        try:
            await self.db.commit()
        except IntegrityError as e:
            await self.db.rollback()
            raise OAuthIdentityAlreadyLinkedError(
                f"{payload.provider} account already linked to a user"
            ) from e
        await self.db.refresh(identity)
        return identity

    async def get_user_by_provider_id(
        self, provider: str, provider_user_id: str
    ) -> UserModel:
        """
        Reverse lookup: given a provider + provider's user id (e.g. Google's
        'sub' claim), return the linked internal user. Used on every OAuth
        login after the first to find the existing account.
        """
        result = await self.db.execute(
            select(UserModel)
            .join(OAuthIdentityModel, OAuthIdentityModel.user_id == UserModel.id)
            .where(
                OAuthIdentityModel.provider == provider,
                OAuthIdentityModel.provider_user_id == provider_user_id,
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise UserNotFoundError(
                f"No user linked to {provider} account {provider_user_id}"
            )
        return user