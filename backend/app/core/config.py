"""Application configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Look for .env in backend/ first, then project root
_backend_dir = Path(__file__).resolve().parent.parent.parent
_env_files = [p for p in [_backend_dir / ".env", _backend_dir.parent / ".env"] if p.exists()]


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://localhost:5432/scc_intel"

    # API keys
    groq_api_key: str = ""
    openai_api_key: str = ""

    # App
    environment: str = "development"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
	"http://localhost:5175",  # Add this line
        "https://scc-intel-dashboard.onrender.com",
    ]

    # Scraper config
    tender_board_base_url: str = "https://etendering.tenderboard.gov.om"
    scrape_max_pages: int = 10
    scrape_page_delay: float = 1.0

    # SCC profile
    scc_categories: list[str] = [
        "Construction", "Ports", "Roads", "Bridges",
        "Pipeline", "Electromechanical", "Dams", "Marine",
    ]
    scc_grades: list[str] = ["Excellent", "First", "Second"]
    scc_competitors: list[str] = [
        "Galfar", "Strabag", "Al Tasnim", "L&T",
        "Towell", "Hassan Allam", "Arab Contractors", "Ozkar",
    ]

    model_config = {
        "env_file": _env_files if _env_files else ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
