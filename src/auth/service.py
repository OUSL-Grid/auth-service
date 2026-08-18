

from datetime import UTC, datetime, timedelta

from src.auth.magic_link import generate_token, hash_token
from src.db.schemas import OTPCodeCreate, UserCreate
from src.db.user_repository import UserRepository
from src.db.otp_repository import OTPRepository
from src.auth.domain_whitelist import DomainWhitelist
from src.email.client import EmailClient
from src.core.exceptions import UserNotFoundError, RateLimitExceededError


class MagicLinkService:
    def __init__(
            self,
            user_repo: UserRepository, 
            otp_repo: OTPRepository,
            whitelist: DomainWhitelist,
            email_client: EmailClient,
            base_url: str,
            token_expiry_minutes: int = 15,
            rate_limit_max: int = 3,
            rate_limit_window_minutes: int = 15,
    ):
        self.user_repo = user_repo
        self.otp_repo = otp_repo
        self.whitelist = whitelist
        self.email_client = email_client
        self.base_url = base_url
        self.token_expiry_minutes = token_expiry_minutes
        self.rate_limit_max = rate_limit_max
        self.rate_limit_window_minutes = rate_limit_window_minutes

    async def request_magic_link(self, email: str) -> None:
        # 1. domain validation before anything else (reject before touching the DB)
        verified_domain = self.whitelist.validate(email)

        # 2. find or create the user
        try:
            user = await self.user_repo.get_user_by_email(email)
        except UserNotFoundError as e:
            user = await self.user_repo.create_user(
                UserCreate(email=email, verified_domain=verified_domain)
            ) 

        # 3. rete limit - check before generating a new token
        recent_count = await self.otp_repo.count_recent_codes_for_user(
            user.id, purpose="magic_link", window_minutes=self.rate_limit_window_minutes
        )

        if recent_count >= self.rate_limit_max:
            raise RateLimitExceededError(
                "Too many magic link requests. Please wait before trying again."
            )

        # 4. generate and hash the toke
        raw_token = generate_token()
        token_hash = hash_token(raw_token)

        # 5. store the hash, never the raw token
        await self.otp_repo.create_code(
            OTPCodeCreate(
                user_id=user.id,
                code_hash=token_hash,
                purpose="magic_link",
                expires_at=datetime.now(UTC) + timedelta(minutes=self.token_expiry_minutes),
            )
        )

        # 6. email the raw token 
        link_url = f"{self.base_url}/auth/verify?token={raw_token}"
        await self.email_client.send_magic_link(email, link_url)






