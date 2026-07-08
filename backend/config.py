import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the .env file path relative to this config.py file, not the CWD.
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8")

    APP_NAME: str = "DDR Intelligence Portal Backend"
    DEBUG_MODE: bool = True
    GROQ_API_KEY: str = ""  # Loaded from .env by pydantic-settings
    GEMINI_API_KEY: str = ""  # Loaded from .env by pydantic-settings

    # Computed directories — not from env
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR: str = os.path.join(BASE_DIR, "output")
    STATIC_DIR: str = os.path.join(BASE_DIR, "static")

settings = Settings()

# Ensure output and static directories exist
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.STATIC_DIR, exist_ok=True)
