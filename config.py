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
    anthropic_model: str = "claude-haiku-4-5"
    digest_hour: int = 8
    digest_minute: int = 0
    webhook_base_url: str = ""  # ex: https://monbot.onrender.com — vide = mode polling local
    port: int = 8443


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
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
        digest_hour=int(os.getenv("DIGEST_HOUR", "8")),
        digest_minute=int(os.getenv("DIGEST_MINUTE", "0")),
        webhook_base_url=os.getenv("WEBHOOK_BASE_URL", ""),
        port=int(os.getenv("PORT", "8443")),
    )
