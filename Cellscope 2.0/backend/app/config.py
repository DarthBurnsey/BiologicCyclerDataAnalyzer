"""Application configuration using Pydantic Settings."""

from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    app_name: str = "CellScope 2.0"
    debug: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./cellscope2.db"
    legacy_database_path: str = str(Path(__file__).resolve().parents[3] / "cellscope.db")

    # Data storage
    data_dir: str = "data/experiments"

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Live collection defaults
    default_timezone: str = "America/Chicago"
    live_poll_default_seconds: int = 300
    live_stable_window_seconds: int = 120
    live_channel_offline_minutes: int = 15
    live_run_completion_hours: int = 12

    # Reporting defaults
    report_hour: int = 7
    report_minute: int = 0
    report_timezone: str = "America/Chicago"
    report_subject_prefix: str = "[CellScope]"

    # SMTP / email delivery
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    report_sender: Optional[str] = None

    @property
    def data_path(self) -> Path:
        """Get the data directory path, creating it if needed."""
        path = Path(self.data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

settings = Settings()
