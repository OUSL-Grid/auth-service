import threading
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    env: str
    database_url_sync: str
    database_url_async: str
    base_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

class MagicLink(BaseModel):
    token_expiry_minutes: int
    rate_limit_max_per_window: int
    rate_limit_window_minutes: int

class Auth(BaseModel):
    allowed_domains: list[str]
    allow_edu_wildcard: bool
    magic_link: MagicLink

class AppConfig(BaseModel):
    name: str
    version: float
    auth: Auth

def load_yaml_config_file(file: str = "config") -> AppConfig:
    config_path = (
        Path(__file__).resolve().parent.parent.parent / "config" / f"{file}.yaml"
    )

    with open(config_path, "r") as f:
        content = yaml.safe_load(f) or {}

    return AppConfig(**content)

class ConfigManager:
    _instance: Optional["ConfigManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self):
        self.settings: Settings = Settings()
        self.app_config: AppConfig = load_yaml_config_file("config")

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        """ Thread-safe Singleton accessor using double-checked locking """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
