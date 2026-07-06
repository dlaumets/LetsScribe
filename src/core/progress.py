"""In-memory progress for active transcription jobs."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable

_lock = threading.Lock()
_store: dict[uuid.UUID, dict] = {}


@dataclass
class ProgressState:
    percent: float = 0.0
    stage: str = "pending"
    partial_text: str = ""
    segments_done: int = 0


ProgressCallback = Callable[[ProgressState], None]


def set_progress(job_id: uuid.UUID, **kwargs) -> None:
    with _lock:
        current = _store.get(job_id, {})
        current.update(kwargs)
        _store[job_id] = current


def get_progress(job_id: uuid.UUID) -> dict | None:
    with _lock:
        return _store.get(job_id, {}).copy() if job_id in _store else None


def clear_progress(job_id: uuid.UUID) -> None:
    with _lock:
        _store.pop(job_id, None)


def make_callback(job_id: uuid.UUID, db_updater: ProgressCallback | None = None) -> ProgressCallback:
    def on_progress(state: ProgressState) -> None:
        set_progress(
            job_id,
            progress_percent=round(state.percent, 1),
            progress_stage=state.stage,
            partial_text=state.partial_text[-800:],
            segments_done=state.segments_done,
        )
        if db_updater:
            db_updater(state)

    return on_progress
