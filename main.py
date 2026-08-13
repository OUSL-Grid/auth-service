from src.utils import ConfigManager


def main():
    cfg_mgr = ConfigManager()
    print(cfg_mgr.app_config.name)
    print(cfg_mgr.settings.env)


if __name__ == "__main__":
    main()
