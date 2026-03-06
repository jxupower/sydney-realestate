from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://realestate:realestate@localhost:5432/realestate"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Domain.com.au API
    domain_client_id: str = ""
    domain_client_secret: str = ""

    # Admin key — protects /api/v1/admin endpoints
    admin_api_key: str = "change-me"

    # Geo constraints
    sydney_cbd_lat: float = -33.8688
    sydney_cbd_lng: float = 151.2093
    search_radius_km: float = 150.0

    # Sentry (optional)
    sentry_dsn: str = ""

    # Data directory (mounted at /data in Docker)
    data_dir: str = "/data"


settings = Settings()
