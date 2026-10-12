from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.claims import Claims, decode_access_token
from src.auth.domain_whitelist import DomainWhitelist
from src.auth.jwt import TokenService
from src.auth.service import MagicLinkService
from src.core.config import ConfigManager
from src.core.exceptions import TokenExpiredError, TokenInvalidError
from src.db.otp_repository import OTPRepository
from src.db.session import get_db_session
from src.db.session_repository import SessionRepository
from src.db.user_repository import UserRepository
from src.email.client import ConsoleEmailClient, EmailClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import ConfigManager

# auto_error=False so we control the status code and message (always 401)
bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


@lru_cache
def get_domain_whitelist() -> DomainWhitelist:
    cfg_mgr = ConfigManager()

    return DomainWhitelist(
        allowed_domains=cfg_mgr.app_config.auth.allowed_domains,
        allow_edu_wildcard=cfg_mgr.app_config.auth.allow_edu_wildcard,
    )


@lru_cache
def get_email_client() -> EmailClient:
    # TODO: swap ConsoleEmailClient for a real provider
    return ConsoleEmailClient()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    # Pass empty string since singleton is already initialized in lifespan
    async with get_db_session("") as session:
        yield session

@lru_cache
def get_private_key() -> str:
    config = ConfigManager.get_instance()
    
    with open(config.app_config.jwts.private_key_path) as f:
        return f.read()

@lru_cache
def get_public_key() -> str:
    config = ConfigManager.get_instance()
    
    with open(config.app_config.jwts.public_key_path) as f:
        return f.read()

def get_jwt_issuer() -> str:
    config = ConfigManager.get_instance()
    return config.app_config.jwts.issuer

def get_token_service(db: AsyncSession = Depends(get_db)) -> TokenService:
    config = ConfigManager.get_instance()
    return TokenService(
        private_key=get_private_key(),
        session_repo=SessionRepository(db),
        user_repo=UserRepository(db),
        access_ttl_minutes=config.app_config.jwts.access_token_expiry_minutes,
        refresh_ttl_days=config.app_config.jwts.refresh_token_expiry_days,
        issuer=config.app_config.jwts.issuer,
    )


def get_magic_link_service(
    db: AsyncSession = Depends(get_db),
    whitelist: DomainWhitelist = Depends(get_domain_whitelist),
    email_client: EmailClient = Depends(get_email_client),
    token_service: TokenService = Depends(get_token_service),
) -> MagicLinkService:
    cfg_mgr = ConfigManager()
    app_config = cfg_mgr.app_config
    settings = cfg_mgr.settings

    return MagicLinkService(
        user_repo=UserRepository(db),
        otp_repo=OTPRepository(db),
        whitelist=whitelist,
        email_client=email_client,
        token_service=token_service,
        base_url=settings.base_url, 
        token_expiry_minutes=app_config.auth.magic_link.token_expiry_minutes,
        rate_limit_max=app_config.auth.magic_link.rate_limit_max_per_window,
        rate_limit_window_minutes=app_config.auth.magic_link.rate_limit_window_minutes,
    )

async def get_current_claims(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    public_key: str = Depends(get_public_key),
    issuer: str = Depends(get_jwt_issuer),
) -> Claims:
    if credentials is None:
        raise HTTPException(401, "Missing bearer token", headers=_UNAUTHORIZED_HEADERS)

    try:
        claims = decode_access_token(credentials.credentials, public_key, issuer)
    except TokenExpiredError:
        raise HTTPException(401, "Access token has expired", headers=_UNAUTHORIZED_HEADERS)
    except TokenInvalidError:
        raise HTTPException(401, "Invalid access token", headers=_UNAUTHORIZED_HEADERS)

    request.state.claims = claims
    return claims

import os

from src.auth.google_service import GoogleAuthService
from src.auth.oauth_google import GoogleOAuthClient, OAuthStateCodec
from src.core.security import TokenCipher
from src.db.oauth_repository import OAuthRepository


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required for Google sign-in")
    return value


@lru_cache
def get_google_client() -> GoogleOAuthClient:
    config = ConfigManager.get_instance()

    return GoogleOAuthClient(
        client_id=config.app_config.google_settings.client_id,
        client_secret=_require_env("GOOGLE_CLIENT_SECRET"),
        redirect_uri=config.app_config.google_settings.redirect_uri,
        hosted_domain_hint=config.app_config.google_settings.hosted_domain_hint,
    )


@lru_cache
def get_state_codec() -> OAuthStateCodec:
    return OAuthStateCodec(_require_env("OAUTH_STATE_SECRET"))


@lru_cache
def get_token_cipher() -> TokenCipher | None:
    key = os.environ.get("TOKEN_ENCRYPTION_KEY")
    return TokenCipher(key) if key else None


def get_cookie_secure() -> bool:
    config = ConfigManager.get_instance()
    return config.app_config.google_settings.cookie_secure



def get_google_auth_service(
    db: AsyncSession = Depends(get_db),
    google: GoogleOAuthClient = Depends(get_google_client),
    whitelist: DomainWhitelist = Depends(get_domain_whitelist),
    token_service: TokenService = Depends(get_token_service),
    cipher: TokenCipher | None = Depends(get_token_cipher),
) -> GoogleAuthService:
    return GoogleAuthService(
        google=google,
        user_repo=UserRepository(db),
        oauth_repo=OAuthRepository(db),
        otp_repo=OTPRepository(db),
        whitelist=whitelist,
        token_service=token_service,
        cipher=cipher,
    )

def get_frontend_url() -> str:
    config = ConfigManager.get_instance()
    return config.app_config.app.frontend_url.rstrip("/")