from pydantic import Field
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        alias="OLLAMA_BASE_URL",
    )
    ollama_model: str = Field(
        default="qwen2.5:3b",
        alias="OLLAMA_MODEL",
    )
    database_url: str = Field(
        default="postgresql://assess:assess@localhost:5432/analytics",
        alias="DATABASE_URL",
    )
    mcp_server_url: str = Field(
        default="http://localhost:8001/mcp",
        alias="MCP_SERVER_URL",
    )

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_settings() -> Settings:
    return Settings()