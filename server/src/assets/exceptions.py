class AssetNotFound(Exception):
    def __init__(self, message: str = "Asset not found") -> None:
        super().__init__(message)


class InvalidAsset(Exception):
    def __init__(self, message: str = "Invalid asset payload") -> None:
        super().__init__(message)


class AssetUploadNotReady(Exception):
    def __init__(self, message: str = "Asset upload is not ready to finalize") -> None:
        super().__init__(message)
