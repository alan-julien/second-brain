import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    telegram_token: str
    telegram_user_id: int
    anthropic_api_key: str
    notion_token: str
    notion_database_id: str
    digest_hour: int = 8
    digest_minute: int = 0


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_config() -> Config:
    load_dotenv()

    return Config(
        telegram_token=_required_env("TELEGRAM_TOKEN"),
        telegram_user_id=int(_required_env("TELEGRAM_USER_ID")),
        anthropic_api_key=_required_env("ANTHROPIC_API_KEY"),
        notion_token=_required_env("NOTION_TOKEN"),
        notion_database_id=_required_env("NOTION_DATABASE_ID"),
        digest_hour=int(os.getenv("DIGEST_HOUR", "8")),
        digest_minute=int(os.getenv("DIGEST_MINUTE", "0")),
    )
