from enum import StrEnum

MAX_DATASET_NAME_LENGTH = 200
MAX_IMPORT_ROWS = 5000
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_CONTENT_CHARS = 50_000
CONVERSATION_PREVIEW_LIMIT = 50
MAX_TOP_K = 50
DEFAULT_TOP_K = 12
MAX_REPORTS_LIST = 200
MAX_COLLECTOR_PER_STORE = 100
MASTER_DATASET_SOURCE = "other"

ALLOWED_SOURCES = (
    "google_play",
    "app_store",
    "reddit",
    "youtube",
    "csv",
    "other",
)

IMPORTABLE_STATUSES = {"pending", "imported", "failed", "ready", "indexing"}
# ready/indexing: append allowed; status returns to imported for Phase 3 reindex
BLOCKED_IMPORT_STATUSES = {"processing", "indexing"}


class DatasetStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    IMPORTED = "imported"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
