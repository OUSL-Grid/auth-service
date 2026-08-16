
from src.core import ConfigManager


def test_app_config_manager_success():
    cfg_mgr = ConfigManager()
    assert cfg_mgr.app_config.name is not None
    assert cfg_mgr.app_config.auth.allowed_domains is not None

def test_settings_config_manager_success():
    cfg_mgr = ConfigManager()
    assert cfg_mgr.settings.env is not None
    assert cfg_mgr.settings.database_url_sync is not None
    