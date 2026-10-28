from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./data/schemesaarthi.db"
    secret_key: str = "dev-only-change-me-before-deployment"
    frontend_url: str = "http://localhost:5173"
    llm_provider: str = "none"
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    max_upload_mb: int = 10
    admin_bootstrap_secret: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
settings = Settings()
