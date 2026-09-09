import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GEMINI_API_KEY: str = "test_key"
    GEMINI_MODEL: str = "gemini-3.6-flash"
    DATABASE_URL: str = "sqlite:///./pde.db"
    SECRET_KEY: str = "default-insecure-key-for-local-dev-only"
    ENVIRONMENT: str = "development"
    FRONTEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        if self.ENVIRONMENT == "production":
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("DATABASE_URL must be a PostgreSQL connection string in production!")
            if self.SECRET_KEY == "default-insecure-key-for-local-dev-only":
                raise ValueError("SECRET_KEY must be overridden in production!")


settings = Settings()
