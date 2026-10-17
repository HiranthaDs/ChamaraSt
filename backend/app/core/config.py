from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env", override=False)

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "").strip()
    app_env: str = os.getenv("APP_ENV", "development").strip()
    api_host: str = os.getenv("API_HOST", "127.0.0.1").strip()
    api_port: int = int(os.getenv("API_PORT", "8000"))
    frontend_origins: tuple[str, ...] = tuple(
        origin.strip() for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174",
        ).split(",") if origin.strip()
    )

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url.startswith(("postgresql://", "postgres://"))
                    and "YOUR_" not in self.database_url)

settings = Settings()
