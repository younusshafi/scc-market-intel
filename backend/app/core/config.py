"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://localhost:5432/scc_intel"

    # API keys
    groq_api_key: str = ""

    # App
    environment: str = "development"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
