from datetime import datetime, timezone
from threading import Lock


TASKS = {}
TASK_LOCK = Lock()


def create_task(task_id: str) -> None:
    """Register a new indexing task."""

    now = datetime.now(timezone.utc).isoformat()

    with TASK_LOCK:
        TASKS[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "stage": "queued",
            "files_scanned": 0,
            "files_processed": 0,
            "files_chunked": 0,
            "chunks_total": 0,
            "chunks_indexed": 0,
            "percent": 0,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }


def update_task(task_id: str, **updates) -> None:
    """Update task status and progress."""

    with TASK_LOCK:
        task = TASKS.get(task_id)

        if task is None:
            return

        task.update(updates)

        task["updated_at"] = (
            datetime.now(timezone.utc).isoformat()
        )


def get_task(task_id: str) -> dict | None:
    """Return a copy of the requested task."""

    with TASK_LOCK:
        task = TASKS.get(task_id)

        return task.copy() if task else None