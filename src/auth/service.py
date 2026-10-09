

from datetime import UTC, datetime, timedelta

from src.auth.jwt import TokenPair
from src.auth.magic_link import generate_token, hash_token
from src.db.schemas import OTPCodeCreate, UserCreate
from src.db.user_repository import UserRepository
from src.db.otp_repository import OTPRepository
from src.auth.domain_whitelist import DomainWhitelist
from src.email.client import EmailClient
from src.core.exceptions import AccountDisabledError, CodeConsumedError, UserNotFoundError, RateLimitExceededError, CodeNotFoundError


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
        self.whitelist.validate(email)


        recent_count = await self.otp_repo.count_recent_codes_for_email(
            email, purpose="magic_link", window_minutes=self.rate_limit_window_minutes
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
                email=email,
                code_hash=token_hash,
                purpose="magic_link",
                expires_at=datetime.now(UTC) + timedelta(minutes=self.token_expiry_minutes),
            )
        )

        # 6. email the raw token 
        link_url = f"{self.base_url}/auth/verify?token={raw_token}"
        await self.email_client.send_magic_link(email, link_url)




    async def verify_magic_link(
        self, raw_token: str, user_agent: str | None = None, ip_address: str | None = None
    ) -> TokenPair:
        code = await self.otp_repo.get_valid_code_by_hash(hash_token(raw_token))

        if code.purpose != "magic_link":
            raise CodeNotFoundError("code not recognized")

        if not await self.otp_repo.mark_consumed(code.id):
            raise CodeConsumedError("Code has already been used")

        try:
            user = await self.user_repo.get_user_by_email(code.email)
        except UserNotFoundError:
            verified_domain = self.whitelist.validate(code.email)
            user = await self.user_repo.create_user(
                UserCreate(email=code.email, verified_domain=verified_domain, role="student")
            )

        if not user.active:
            raise AccountDisabledError("This account has been disabled")

        return await self.token_service.issue_token_pair(user, user_agent, ip_address)

