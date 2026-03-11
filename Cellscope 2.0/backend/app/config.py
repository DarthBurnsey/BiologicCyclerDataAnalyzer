"""Application configuration using Pydantic Settings."""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "CellScope 2.0"
    debug: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./cellscope2.db"

    # Data storage
    data_dir: str = "data/experiments"

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    @property
    def data_path(self) -> Path:
        """Get the data directory path, creating it if needed."""
        path = Path(self.data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
