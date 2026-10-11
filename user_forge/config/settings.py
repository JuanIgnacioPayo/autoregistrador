import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    VAULT_DIR: Path = BASE_DIR / "vault_data"
    DB_PATH: Path = VAULT_DIR / "user_forge_vault.db"
    KEY_PATH: Path = VAULT_DIR / ".master.key"
    PROFILES_DIR: Path = BASE_DIR / "browser_profiles"
    
    DEFAULT_EMAIL_DOMAIN: str = "example.com"
    DEFAULT_CATCHALL_BASE: str = "mycatchall@example.com"
    EMAIL_STRATEGY: str = "plus"  # 'plus' (user+alias@domain.com) or 'direct' (alias@domain.com)
    DEFAULT_LOCALE: str = "es_AR"
    
    HEADLESS_DEFAULT: bool = False
    BROWSER_TIMEOUT_MS: int = 45000

    class Config:
        env_prefix = "USERFORGE_"
        env_file = ".env"
        extra = "ignore"

settings = Settings()
settings.VAULT_DIR.mkdir(parents=True, exist_ok=True)
settings.PROFILES_DIR.mkdir(parents=True, exist_ok=True)
