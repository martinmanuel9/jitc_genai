"""
Application configuration management using Pydantic Settings.

This module centralizes all environment-based configuration for the application,
providing type-safe access to configuration values with validation.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache
import logging 

logger = logging.getLogger('CORE_CONFIG')


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Attributes:
        app_name: Name of the application
        debug: Debug mode flag

        # Database Configuration
        db_username: PostgreSQL username
        db_password: PostgreSQL password
        db_host: PostgreSQL host
        db_endpoint: AWS RDS endpoint (alternative to db_host)
        db_port: PostgreSQL port
        db_name: PostgreSQL database name
        database_url: Complete database URL (if provided directly)

        # Connection Pool Settings
        db_pool_size: Database connection pool size
        db_max_overflow: Maximum overflow connections
        db_pool_timeout: Pool checkout timeout in seconds
        db_pool_recycle: Connection recycle time in seconds

        # ChromaDB Configuration
        chroma_host: ChromaDB host
        chroma_port: ChromaDB port

        # Redis Configuration
        redis_url: Redis connection URL

        # API Keys
        openai_api_key: OpenAI API key
    """

    # Application Settings
    app_name: str = "Litigation GenAI"
    debug: bool = False
    environment: str = "development"

    # Database Configuration
    db_username: str = "postgres"
    db_password: Optional[str] = None
    db_host: Optional[str] = None
    db_endpoint: Optional[str] = None  # AWS RDS style
    db_port: str = "5432"
    db_name: Optional[str] = None
    dbname: Optional[str] = None  # Alternative naming
    postgres_db: str = "rag_memory"  # Fallback
    database_url: Optional[str] = None

    # Connection Pool Settings
    db_pool_size: int = 20
    db_max_overflow: int = 30
    db_pool_timeout: int = 10
    db_pool_recycle: int = 3600
    db_pool_pre_ping: bool = True
    db_echo: bool = False

    # ChromaDB Configuration (internal Docker port is 8000, external host port is 8001)
    chroma_host: str = "chromadb"
    chroma_port: int = 8000

    # Redis Configuration
    redis_url: str = "redis://redis:6379/0"

    # API Keys
    openai_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from environment

    def get_database_name(self) -> str:
        """Get the database name from various possible environment variables."""
        return self.db_name or self.dbname or self.postgres_db

    def get_database_host(self) -> str:
        """
        Get database host, parsing DB_ENDPOINT if necessary.

        Returns:
            str: Database host address

        Raises:
            ValueError: If no host configuration is found
        """
        # If DB_ENDPOINT is provided, parse it
        if self.db_endpoint:
            if ':' in self.db_endpoint:
                parts = self.db_endpoint.rsplit(':', 1)
                potential_host = parts[0]
                potential_port = parts[1]

                try:
                    int(potential_port)
                    # Valid port found, update port if not explicitly set
                    if not os.getenv("DB_PORT"):
                        self.db_port = potential_port
                    return potential_host
                except ValueError:
                    # Not a valid port, use entire endpoint as host
                    return self.db_endpoint
            else:
                return self.db_endpoint

        # Fall back to DB_HOST
        if self.db_host:
            return self.db_host

        raise ValueError("Database host configuration missing (DB_HOST or DB_ENDPOINT)")

    def get_database_url(self) -> str:
        """
        Construct the database URL from components or return direct URL.

        Returns:
            str: PostgreSQL database URL

        Raises:
            ValueError: If required configuration is missing
        """
        # If DATABASE_URL is directly provided, use it
        if self.database_url:
            return self.database_url

        # Validate required components
        missing = []
        if not self.db_username:
            missing.append("DB_USERNAME")
        if not self.db_password:
            missing.append("DB_PASSWORD")

        db_name = self.get_database_name()
        if not db_name:
            missing.append("DB_NAME or DBNAME")

        try:
            db_host = self.get_database_host()
        except ValueError:
            missing.append("DB_HOST or DB_ENDPOINT")
            db_host = None

        if missing:
            raise ValueError(f"Database configuration incomplete. Missing: {', '.join(missing)}")

        # Construct URL
        url = f"postgresql://{self.db_username}:{self.db_password}@{db_host}:{self.db_port}/{db_name}"
        return url


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Settings: Cached settings object
    """
    return Settings()
