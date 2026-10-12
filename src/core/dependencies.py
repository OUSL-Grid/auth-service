from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends

from src.auth.domain_whitelist import DomainWhitelist
from src.auth.jwt import TokenService
from src.auth.service import MagicLinkService
from src.core.config import ConfigManager
from src.db.otp_repository import OTPRepository
from src.db.session import get_db_session
from src.db.session_repository import SessionRepository
from src.db.user_repository import UserRepository
from src.email.client import ConsoleEmailClient, EmailClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import ConfigManager


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


def get_token_service(db: AsyncSession = Depends(get_db)) -> TokenService:
    config = ConfigManager.get_instance()
    return TokenService(
        private_key=get_private_key(),
        session_repo=SessionRepository(db),
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