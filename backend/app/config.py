import os
import json
from typing import Union
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GEMINI_API_KEY: str = "test_key"
    GEMINI_MODEL: str = "gemini-3.6-flash"
    DATABASE_URL: str = "sqlite:///./pde.db"
    SECRET_KEY: str = "default-insecure-key-for-local-dev-only"
    ENVIRONMENT: str = "development"
    FRONTEND_CORS_ORIGINS: Union[list[str], str] = [
        "http://localhost:3000",
        "https://personal-decision-engine.vercel.app",
    ]

    class Config:
        env_file = ".env"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_db_url(cls, v: str) -> str:
        if v and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    @field_validator("FRONTEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, list[str]]) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    pass
            if "," in v:
                return [i.strip() for i in v.split(",") if i.strip()]
            return [v]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.ENVIRONMENT == "production":
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("DATABASE_URL must be a PostgreSQL connection string in production!")
            if self.SECRET_KEY == "default-insecure-key-for-local-dev-only":
                raise ValueError("SECRET_KEY must be overridden in production!")


settings = Settings()
