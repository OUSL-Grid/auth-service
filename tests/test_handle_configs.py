
from src.utils import ConfigManager


def test_app_config_manager_success():
    cfg_mgr = ConfigManager()
    assert cfg_mgr.app_config.name == "auth-service"

def test_settings_config_manager_success():
    cfg_mgr = ConfigManager()
    assert cfg_mgr.settings.env == "develop"
    