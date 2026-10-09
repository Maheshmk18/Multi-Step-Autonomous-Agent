import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "agent_assistant"
    mongodb_data_uri: str | None = None
    mongodb_data_database: str = "agent_data"
    mongodb_allowed_collections: str = ""
    tavily_api_key: str | None = None
    gmail_credentials_path: Path = Path(".secrets/credentials.json")
    gmail_token_path: Path = Path(".secrets/gmail-token.json")
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "multi-agent-assistant"
    cors_origins: str = "http://localhost:5173"
    max_request_chars: int = 8000
    max_graph_steps: int = 8
    max_agent_tool_calls: int = 8

    @property
    def allowed_collections(self) -> set[str]:
        return {
            name.strip()
            for name in self.mongodb_allowed_collections.split(",")
            if name.strip()
        }

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

if settings.langsmith_tracing and settings.langsmith_api_key:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
