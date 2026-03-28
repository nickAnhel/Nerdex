from src.config import AssetsSettings, CelerySettings, RedisSettings, StorageSettings


def test_new_config_sections_read_from_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("STORAGE_ENDPOINT_URL", "https://s3.storage.selcloud.ru")
    monkeypatch.setenv("STORAGE_REGION", "ru-1")
    monkeypatch.setenv("STORAGE_ACCESS_KEY", "key")
    monkeypatch.setenv("STORAGE_SECRET_KEY", "secret")
    monkeypatch.setenv("STORAGE_PRIVATE_BUCKET", "nerdex-dev-private")
    monkeypatch.setenv("STORAGE_USE_SSL", "true")
    monkeypatch.setenv("STORAGE_ADDRESSING_STYLE", "path")
    monkeypatch.setenv("STORAGE_PRESIGNED_UPLOAD_TTL_SECONDS", "900")
    monkeypatch.setenv("STORAGE_PRESIGNED_DOWNLOAD_TTL_SECONDS", "600")
    monkeypatch.setenv("ASSETS_MAX_IMAGE_SIZE_MB", "20")
    monkeypatch.setenv("ASSETS_MAX_VIDEO_SIZE_MB", "250")
    monkeypatch.setenv("ASSETS_MAX_FILE_SIZE_MB", "50")
    monkeypatch.setenv("ASSETS_ORPHAN_GRACE_HOURS", "24")
    monkeypatch.setenv("ASSETS_STALE_UPLOAD_GRACE_HOURS", "12")
    monkeypatch.setenv("ASSETS_MULTIPART_PART_SIZE_MB", "10")
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_DB", "0")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
    monkeypatch.setenv("CELERY_MEDIA_QUEUE_NAME", "media")

    storage = StorageSettings()
    assets = AssetsSettings()
    redis = RedisSettings()
    celery = CelerySettings()

    assert storage.private_bucket == "nerdex-dev-private"
    assert storage.addressing_style == "path"
    assert assets.max_video_size_mb == 250
    assert redis.url == "redis://redis:6379/0"
    assert celery.media_queue_name == "media"
