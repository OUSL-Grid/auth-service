from functools import lru_cache

from src.auth.domain_whitelist import DomainWhitelist
from src.core.config import ConfigManager


@lru_cache
def get_domain_whitelist() -> DomainWhitelist:
    cfg_mgr = ConfigManager()

    return DomainWhitelist(
        allowed_domains=cfg_mgr.app_config.auth.allowed_domains,
        allow_edu_wildcard=cfg_mgr.app_config.auth.allow_edu_wildcard,
    )