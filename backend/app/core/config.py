"""
Application configuration loaded from environment variables.
Never commit secrets; use a local .env file (see README).
"""
from functools import lru_cache
import json
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── PostgreSQL (Sales Chatbot) ─────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/business_chatbot",
        alias="DATABASE_URL",
        description="SQLAlchemy database URL",
    )

    # ── OpenRouter (Sales Chatbot / Intent Router) ─────────────────────────
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    openrouter_model: str = Field(
        default="meta-llama/llama-3.1-8b-instruct",
        alias="OPENROUTER_MODEL",
    )
    text_to_sql_model: str = Field(
        default="meta-llama/llama-3.3-70b-instruct",
        alias="TEXT_TO_SQL_MODEL",
    )
    sqlcoder_model: str = Field(
        default="defog/sqlcoder-70b-alpha",
        alias="SQLCODER_MODEL",
    )

    # ── Paths ──────────────────────────────────────────────────────────────
    data_dir: str = Field(default="data", alias="DATA_DIR")
    sales_excel_path: str = Field(default="data/Sales Info V2 .xlsx", alias="SALES_EXCEL_PATH")
    timesheet_excel_path: str = Field(
        default="data/Timesheet.xlsx", alias="TIMESHEET_EXCEL_PATH"
    )

    # ── Quotas ─────────────────────────────────────────────────────────────
    default_sales_quota_gbp: float = Field(default=200_000.0, alias="DEFAULT_SALES_QUOTA_GBP")
    sales_quotas_json: str | None = Field(default=None, alias="SALES_QUOTAS_JSON")

    def parsed_sales_quotas(self) -> dict[str, float]:
        if not self.sales_quotas_json:
            return {}
        try:
            raw: dict[str, Any] = json.loads(self.sales_quotas_json)
            return {str(k): float(v) for k, v in raw.items()}
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}

    # ── Construction AI Settings (from temp_estimation_system) ──────────────
    LOGS_DIR: str = "logs"
    JSON_PATH: str = "data/historical_certification_data.json"
    DB_PATH: str = "data/retrieval.db"
    FAISS_PATH: str = "data/faiss.index"
    ID_MAP_PATH: str = "data/faiss_id_map.pkl"
    EMBEDDINGS_CACHE: str = "data/embeddings.pkl"

    # Model Settings
    MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    BATCH_SIZE: int = 64

    # Retrieval Settings
    DEFAULT_TOP_K: int = 5
    DEFAULT_MIN_TECHNICALITY: float = 0.3
    VECTOR_WEIGHT: float = 0.7
    METADATA_BOOST_WEIGHT: float = 0.3
    DIVERSITY_PER_DOC: int = 3

    # API Settings
    API_TITLE: str = "Construction AI — Knowledge & Retrieval API"
    API_VERSION: str = "1.0.0"
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000

    # Confidence Thresholds
    HIGH_CONFIDENCE_THRESHOLD: float = 0.75
    MEDIUM_CONFIDENCE_THRESHOLD: float = 0.50

    # Groq Settings
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_MAX_TOKENS: int = 1024
    GROQ_TEMPERATURE: float = 0.2


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
