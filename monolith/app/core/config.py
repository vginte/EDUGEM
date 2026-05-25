from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STORE_")

    app_name: str = "EDUGEM Store Monolith"
    app_version: str = "1.0.0"
    debug: bool = False
    data_dir: Path = Path("/app/data")
    events_log_file: str = "events.jsonl"


settings = Settings()
