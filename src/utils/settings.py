from pathlib import Path
from datetime import datetime
from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
import sys

# -------------------------------------------------------------------
# Load .env file deterministically from project root
# -------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

if not ENV_PATH.exists():
    raise FileNotFoundError(f".env file not found at expected location: {ENV_PATH}")

load_dotenv(dotenv_path=ENV_PATH)


# -------------------------------------------------------------------
# Settings Schema
# -------------------------------------------------------------------

class Settings(BaseSettings):
    # ---------------------------------------------------------------
    # Core Metadata
    # ---------------------------------------------------------------

    project_name: str = Field(default="Ind_Fin_XBRL")
    environment: str = Field(default="development")
    
    # ---------------------------------------------------------------
    # Root Paths
    # ---------------------------------------------------------------
    
    root_path: Path = Field(default=PROJECT_ROOT)
    data_path: Path = Field(default=PROJECT_ROOT / "data")

    # ---------------------------------------------------------------
    # Data Paths
    # ---------------------------------------------------------------

    raw_data_path: Path = Field(default=PROJECT_ROOT / "data" / "raw")
    processed_data_path: Path = Field(default=PROJECT_ROOT / "data" / "processed")
    taxonomy_path: Path = Field(default=PROJECT_ROOT / "data" / "taxonomy")
    artifacts_path: Path = Field(default=PROJECT_ROOT / "data" / "artifacts")
    logs_path: Path = Field(default=PROJECT_ROOT / "logs")

    # ---------------------------------------------------------------
    # Neo4j Configuration
    # ---------------------------------------------------------------

    neo4j_uri: str = Field(default="bolt://localhost:7687", validation_alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    neo4j_password: str = Field(default="password", validation_alias="NEO4J_PASSWORD")

    # ---------------------------------------------------------------
    # Runtime Metadata (Deterministic Capture)
    # ---------------------------------------------------------------

    processing_timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    python_version: str = Field(default_factory=lambda: sys.version)

    # ---------------------------------------------------------------
    # ---------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    model_config = ConfigDict(
        env_file=str(ENV_PATH),
        case_sensitive=False,
        extra="ignore"
    )


# -------------------------------------------------------------------
# Singleton Instance
# -------------------------------------------------------------------

settings = Settings()


def get_settings() -> Settings:
    """Get the settings singleton instance."""
    return settings
