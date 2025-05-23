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
    access_key: str
    secret_key: str
    bucket_name: str
    bucket_url: str
    storage_url: str

    model_config = SettingsConfigDict(env_prefix="storage_")


class FilePrefixesSettings(ConfigBase):
    profile_photo_small: str = "PPs@"
    profile_photo_medium: str = "PPm@"
    profile_photo_large: str = "PPl@"


class Settings(BaseSettings):
    db: DBSettings = Field(default_factory=DBSettings)  # type: ignore
    logging: LoggingConfig = Field(default_factory=LoggingConfig)  # type: ignore
    cors: CORSSettings = Field(default_factory=CORSSettings)  # type: ignore
    project: ProjectSettings = Field(default_factory=ProjectSettings)  # type: ignore
    admin: AdminSettings = Field(default_factory=AdminSettings)  # type: ignore
    ws: WebsocketSettings = Field(default_factory=WebsocketSettings)  # type: ignore
    storage: StorageSettings = Field(default_factory=StorageSettings)  # type: ignore
    file_prefixes: FilePrefixesSettings = Field(default_factory=FilePrefixesSettings)  # type: ignore


settings = Settings()
