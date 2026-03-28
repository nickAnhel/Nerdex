from contextlib import asynccontextmanager

from botocore.config import Config

from src.config import settings

try:
    from aiobotocore.session import get_session
except ModuleNotFoundError:  # pragma: no cover - lightweight unit-test envs
    get_session = None


class S3Client:
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        endpoint_url: str,
        region: str,
        use_ssl: bool,
        verify_ssl: bool,
        addressing_style: str,
    ) -> None:
        normalized_endpoint_url = endpoint_url.rstrip("/")
        self._config = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "endpoint_url": normalized_endpoint_url,
            "region_name": region,
            "use_ssl": use_ssl,
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": addressing_style},
            ),
        }
        self._bucket_name = bucket_name
        self._verify_ssl = verify_ssl
        self._session = None if get_session is None else get_session()

    @asynccontextmanager
    async def get_client(self):
        if self._session is None:
            raise RuntimeError("aiobotocore is required to use S3Client")
        async with self._session.create_client(
            "s3",
            **self._config,
            verify=self._verify_ssl,
        ) as client:
            yield client

    async def upload_file(
        self,
        file: bytes,
        filename: str,
    ) -> None:
        async with self.get_client() as client:  # type: ignore
            res = await client.put_object(  # type: ignore
                Bucket=self._bucket_name,
                Key=filename,
                Body=file,
            )
            return res["ResponseMetadata"]["HTTPStatusCode"] == 200

    async def delete_file(
        self,
        filename: str,
    ) -> None:
        async with self.get_client() as client:  # type: ignore
            res = await client.delete_object(  # type: ignore
                Bucket=self._bucket_name,
                Key=filename,
            )
            return res["ResponseMetadata"]["HTTPStatusCode"] == 204


s3_client = S3Client(
    access_key=settings.storage.access_key,
    secret_key=settings.storage.secret_key,
    bucket_name=settings.storage.private_bucket,
    endpoint_url=settings.storage.resolved_endpoint_url,
    region=settings.storage.region,
    use_ssl=settings.storage.use_ssl,
    verify_ssl=settings.storage.verify_ssl,
    addressing_style=settings.storage.addressing_style,
)
