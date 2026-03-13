from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class DBSettings(ConfigBase):
    host: str
    port: str
    name: str
    user: str
    password: str

    echo: bool = False

    model_config = SettingsConfigDict(env_prefix="db_")

    @property
    def db_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class CORSSettings(ConfigBase):
    allowed_hosts: list[str]

    model_config = SettingsConfigDict(env_prefix="cors_")


class ProjectSettings(ConfigBase):
    title: str
    description: str
    version: str
    debug: bool

    model_config = SettingsConfigDict(env_prefix="project_")


class LoggingConfig(ConfigBase):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    model_config = SettingsConfigDict(env_prefix="logging_")


class AdminSettings(ConfigBase):
    secret_key: str
    session_expire_minutes: int

    model_config = SettingsConfigDict(env_prefix="admin_")


class WebsocketSettings(ConfigBase):
    allowed_hosts: list[str]

    model_config = SettingsConfigDict(env_prefix="ws_")


class StorageSettings(ConfigBase):
    endpoint_url: str
    region: str
    access_key: str
    secret_key: str
    private_bucket: str
    use_ssl: bool = True
    addressing_style: Literal["virtual", "path"] = "virtual"
    presigned_upload_ttl_seconds: int = 900
    presigned_download_ttl_seconds: int = 900

    model_config = SettingsConfigDict(env_prefix="storage_")


class AssetsSettings(ConfigBase):
    max_image_size_mb: int = 20
    max_video_size_mb: int = 250
    max_file_size_mb: int = 50
    orphan_grace_hours: int = 24
    stale_upload_grace_hours: int = 24
    multipart_part_size_mb: int = 10

    model_config = SettingsConfigDict(env_prefix="assets_")


class RedisSettings(ConfigBase):
    host: str
    port: int
    db: int = 0

    model_config = SettingsConfigDict(env_prefix="redis_")

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class CelerySettings(ConfigBase):
    broker_url: str
    result_backend: str
    media_queue_name: str = "media"

    model_config = SettingsConfigDict(env_prefix="celery_")


class Settings(BaseSettings):
    db: DBSettings = Field(default_factory=DBSettings)  # type: ignore
    logging: LoggingConfig = Field(default_factory=LoggingConfig)  # type: ignore
    cors: CORSSettings = Field(default_factory=CORSSettings)  # type: ignore
    project: ProjectSettings = Field(default_factory=ProjectSettings)  # type: ignore
    admin: AdminSettings = Field(default_factory=AdminSettings)  # type: ignore
    ws: WebsocketSettings = Field(default_factory=WebsocketSettings)  # type: ignore
    storage: StorageSettings = Field(default_factory=StorageSettings)  # type: ignore
    assets: AssetsSettings = Field(default_factory=AssetsSettings)  # type: ignore
    redis: RedisSettings = Field(default_factory=RedisSettings)  # type: ignore
    celery: CelerySettings = Field(default_factory=CelerySettings)  # type: ignore


settings = Settings()
