from uuid import uuid1

from src.db.repository import create_user
from src.db.schemas import UserCreate
from src.db.session import Database
from src.utils import ConfigManager


def main():
    cfg_mgr = ConfigManager()
    db = Database(db_url=cfg_mgr.settings.database_url)
    print(cfg_mgr.app_config.name)
    print(cfg_mgr.settings.database_url)

    for i in range(10):
        payload = UserCreate(
            email=f"test{i}@gmail.com",
            password=str(uuid1())[:10],
            verified_domain="domain1"
        )

        user = create_user(db.get_session(), payload)
        print(user)


if __name__ == "__main__":
    main()
