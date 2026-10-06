from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/contacts_db"

    jwt_secret_key: str  # required, no default: a known key would let anyone forge tokens
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    email_token_expire_hours: int = 24
    reset_token_expire_minutes: int = 30

    # Redis: cache of the current user + storage for the rate limiter
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    user_cache_ttl_seconds: int = 900

    # Rate limits, format of the `limits` library: "<count>/<period>"
    rate_limit_contacts: str = "30/minute"
    rate_limit_create_contact: str = "5/minute"
    # login / signup / emails: per IP, protects from password guessing and email flooding
    rate_limit_auth: str = "5/minute"
    rate_limit_storage_uri: str | None = None  # default: the Redis above

    # comma separated list, e.g. "http://localhost:3000,http://127.0.0.1:5173"
    cors_origins: str = "http://localhost:3000"

    # SMTP (Mailpit from docker-compose by default)
    mail_server: str = "localhost"
    mail_port: int = 1025
    mail_username: str | None = None
    mail_password: str | None = None
    mail_from: str = "noreply@contacts.local"
    mail_from_name: str = "Contacts API"
    mail_starttls: bool = False
    mail_ssl_tls: bool = False

    # Cloudinary
    cloudinary_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/0"


settings = Settings()
