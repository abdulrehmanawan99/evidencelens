import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg://evidencelens:evidencelens_local@127.0.0.1:55432/evidencelens")
    storage_dir: Path = Path(os.getenv("STORAGE_DIR", ".local/artifacts")).resolve()
    app_origin: str = os.getenv("APP_ORIGIN", "http://127.0.0.1:3000")
    allowed_hosts: str = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")
    local_owner: str = "local-installation"
    max_upload: int = 20 * 1024 * 1024
    max_characters: int = 500_000
    max_documents: int = 25
    max_versions: int = 10
    max_collection_bytes: int = 100 * 1024 * 1024
    max_passages: int = 5000
    max_pdf_pages: int = 100
    parser_seconds: int = 60
    parser_backend: str = os.getenv("PARSER_BACKEND", "auto")
    parser_image: str = os.getenv("PARSER_IMAGE", "evidencelens-parser:1.0.0")
    lease_seconds: int = 30
    job_deadline_seconds: int = 180
    ingestion_deadline_seconds: int = 900
    model_mode: str = os.getenv("MODEL_MODE", "fixture")
    generation_model: str = os.getenv("GENERATION_MODEL", "")
    generation_endpoint: str = os.getenv("GENERATION_ENDPOINT", "https://api.openai.com/v1")
    generation_key: str = os.getenv("GENERATION_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "openai")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_endpoint: str = os.getenv("EMBEDDING_ENDPOINT", "https://api.openai.com/v1")
    embedding_key: str = os.getenv("EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    context_tokens: int = int(os.getenv("CONTEXT_TOKENS", "16000"))
    max_output_tokens: int = 2000
    provider_timeout: int = 45
    chunking_version: str = "page-chunks-v1"
    analysis_version: str = "grounded-evidence-v2"
    temporary_ttl_seconds: int = 3600


settings = Settings()
