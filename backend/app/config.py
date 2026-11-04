import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg://evidencelens:evidencelens_local@127.0.0.1:55432/evidencelens")
    storage_dir: Path = Path(os.getenv("STORAGE_DIR", ".local/artifacts")).resolve()
    app_origin: str = os.getenv("APP_ORIGIN", "http://127.0.0.1:3000")
    local_owner: str = "local-installation"
    max_upload: int = 2 * 1024 * 1024
    max_characters: int = 500_000
    max_documents: int = 25
    lease_seconds: int = 30
    job_deadline_seconds: int = 180


settings = Settings()
