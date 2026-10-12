from datetime import UTC, datetime, timedelta

from src.auth.domain_whitelist import DomainWhitelist
from src.auth.jwt import TokenPair, TokenService
from src.auth.magic_link import generate_token, hash_token
from src.auth.oauth_google import GoogleIdentity, GoogleOAuthClient
from src.core.exceptions import (
    AccountDisabledError,
    CodeConsumedError,
    CodeNotFoundError,
    DomainNotAllowedError,
    OAuthEmailNotVerifiedError,
    OAuthIdentityAlreadyLinkedError,
    UserNotFoundError,
)
from src.core.security import TokenCipher
from src.db.oauth_repository import OAuthRepository
from src.db.otp_repository import OTPRepository
from src.db.schemas import OAuthIdentityCreate, OTPCodeCreate, UserCreate
from src.db.user_repository import UserRepository

LOGIN_CODE_PURPOSE = "oauth_login"
LOGIN_CODE_TTL = timedelta(seconds=120)


class GoogleAuthService:
    PROVIDER = "google"

    def __init__(
        self,
        google: GoogleOAuthClient,
        user_repo: UserRepository,
        oauth_repo: OAuthRepository,
        otp_repo: OTPRepository,
        whitelist: DomainWhitelist,
        token_service: TokenService,
        cipher: TokenCipher | None = None,
    ):
        self.google = google
        self.user_repo = user_repo
        self.oauth_repo = oauth_repo
        self.otp_repo = otp_repo
        self.whitelist = whitelist
        self.token_service = token_service
        self.cipher = cipher

    async def handle_callback(
        self,
        code: str,
        code_verifier: str,
        nonce: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenPair:
        tokens = await self.google.exchange_code(code, code_verifier)
        identity = await self.google.verify_id_token(tokens["id_token"], nonce)

        if not identity.email_verified:
            raise OAuthEmailNotVerifiedError("Your Google account email is not verified")

        # hd is Google's Workspace-domain claim. An email suffix alone doesn't prove
        # Workspace membership, so require hd and check it against the whitelist.
        if not identity.hosted_domain:
            raise DomainNotAllowedError("Please sign in with your university Google account")
        verified_domain = self.whitelist.validate_domain(identity.hosted_domain)
        self.whitelist.validate(identity.email)

        user = await self._resolve_user(identity, verified_domain, tokens.get("access_token"))
        if not user.active:
            raise AccountDisabledError("This account has been disabled")

        raw = generate_token()
        await self.otp_repo.create_code(
            OTPCodeCreate(
                email=user.email,
                user_id=user.id,
                code_hash=hash_token(raw),   # only the hash is stored
                purpose=LOGIN_CODE_PURPOSE,
                expires_at=datetime.now(UTC) + LOGIN_CODE_TTL,
            )
        )
        return raw

    

    async def _resolve_user(
        self, identity: GoogleIdentity, verified_domain: str, google_access_token: str | None
    ):
        # 1. Returning Google user
        try:
            return await self.oauth_repo.get_user_by_provider_id(self.PROVIDER, identity.sub)
        except UserNotFoundError:
            pass

        # 2. First Google login: reuse the account if they already signed in by magic
        #    link, otherwise create it. Linking by email is safe here because the email
        #    is verified and sits in a whitelisted Workspace domain.
        try:
            user = await self.user_repo.get_user_by_email(identity.email)
        except UserNotFoundError:
            user = await self.user_repo.create_user(
                UserCreate(email=identity.email, verified_domain=verified_domain, role="student")
            )

        encrypted = (
            self.cipher.encrypt(google_access_token)
            if self.cipher and google_access_token
            else None
        )
        try:
            await self.oauth_repo.link_oauth_identity(
                OAuthIdentityCreate(
                    user_id=user.id,
                    provider=self.PROVIDER,
                    provider_user_id=identity.sub,
                    access_token_enc=encrypted,
                )
            )
        except OAuthIdentityAlreadyLinkedError:
            # a concurrent callback linked it first
            return await self.oauth_repo.get_user_by_provider_id(self.PROVIDER, identity.sub)
        return user

    async def exchange_login_code(
        self, raw_code: str, user_agent: str | None = None, ip_address: str | None = None
    ) -> TokenPair:
        # raises CodeNotFoundError / CodeExpiredError / CodeConsumedError / CodeLockedError
        code = await self.otp_repo.get_valid_code_by_hash(hash_token(raw_code))

        # purposes keep magic-link tokens and login codes from being swapped for each other
        if code.purpose != LOGIN_CODE_PURPOSE or code.user_id is None:
            raise CodeNotFoundError("Code not recognized")
        if not await self.otp_repo.mark_consumed(code.id):
            raise CodeConsumedError("Code has already been used")

        user = await self.user_repo.get_user_by_id(code.user_id)
        if not user.active:
            raise AccountDisabledError("This account has been disabled")
        return await self.token_service.issue_token_pair(user, user_agent, ip_address)