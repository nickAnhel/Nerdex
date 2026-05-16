from enum import Enum


class RecommendationSyncMode(str, Enum):
    FULL_REBUILD = "full_rebuild"
    INCREMENTAL_SYNC = "incremental_sync"


class RecommendationSyncStateKey(str, Enum):
    MAIN = "main"
