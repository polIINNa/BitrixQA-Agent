"""Конфигурация Telegram бота."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class BotConfig:
    """Настройки бота из переменных окружения."""
    token: str
    tech_support_account_id: str
    operator_id: str
    bot_username: str
    
    @classmethod
    def from_env(cls) -> "BotConfig":
        """Создать конфигурацию из переменных окружения."""
        token = os.getenv("TELEGRAM_API_TOKEN")
        tech_support_account_id = os.getenv("TECH_SUPPORT_ACCOUNT_ID")
        operator_id = os.getenv("OPERATOR_ID")
        bot_username = os.getenv("BOT_USERNAME")
        
        if not all([token, tech_support_account_id, operator_id, bot_username]):
            missing = []
            if not token:
                missing.append("TELEGRAM_API_TOKEN")
            if not tech_support_account_id:
                missing.append("TECH_SUPPORT_ACCOUNT_ID")
            if not operator_id:
                missing.append("OPERATOR_ID")
            if not bot_username:
                missing.append("BOT_USERNAME")
            raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}")
        
        return cls(
            token=token,
            tech_support_account_id=tech_support_account_id,
            operator_id=operator_id,
            bot_username=bot_username,
        )


# Синглтон конфигурации
_config: BotConfig | None = None


def get_config() -> BotConfig:
    """Получить конфигурацию бота."""
    global _config
    if _config is None:
        _config = BotConfig.from_env()
    return _config

