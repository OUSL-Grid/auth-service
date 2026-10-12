
import secrets
import jwt
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel

from src.auth.magic_link import hash_token
from src.db.models import Users
from src.db.schemas import SessionCreate
from src.db.session_repository import SessionRepository


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int # seconds, for the access token

class TokenService:
    def __init__(
        self,
        private_key: str,
        session_repo: SessionRepository,
        access_ttl_minutes: int = 15,
        refresh_ttl_days: int = 7,
        issuer: str = "auth-service",
    ):
        self.private_key = private_key
        self.session_repo = session_repo
        self.access_ttl = timedelta(minutes=access_ttl_minutes)
        self.refresh_ttl = timedelta(days=refresh_ttl_days)
        self.issuer = issuer

    async def issue_token_pair(
        self, user: Users, user_agent: str | None, ip_address: str | None = None
    ) -> TokenPair:

        now = datetime.now(UTC)

        access_token = jwt.encode(
            {
                "sub": user.id,
                "user_id": user.id,
                "verified_domain": user.verified_domain,
                "role": user.role,
                "trust_score": user.trust_score,
                "iss": self.issuer,
                "iat": now,
                "exp": now + self.access_ttl,
            },
            self.private_key,
            algorithm="RS256"
        )

        raw_refresh = secrets.token_urlsafe(48)
        await self.session_repo.create_session(
            SessionCreate(
                user_id=user.id,
                refresh_token_hash=hash_token(raw_refresh),
                expires_at=now + self.refresh_ttl,
                user_agent=user_agent,
                ip_address=ip_address,
            )
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=int(self.access_ttl.total_seconds()),
        )
    