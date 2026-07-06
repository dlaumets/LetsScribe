"""Background worker for async transcription jobs."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from src.core.progress import ProgressState, clear_progress, make_callback, set_progress
from src.core.service import get_transcribe_service
from src.db.jobs import claim_next_pending_job, complete_job, fail_job, update_job_progress
from src.db.repository import get_user_settings, save_transcription
from src.db.session import get_session_factory

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_wake_event = asyncio.Event()


def wake_worker() -> None:
    _wake_event.set()


async def _process_job(job_id, file_path: Path, **params) -> None:
    factory = get_session_factory()
    service = get_transcribe_service()
    lang = None if params["language"] == "auto" else params["language"]

    set_progress(job_id, progress_percent=0, progress_stage="queued", partial_text="")
    last_db_sync = 0.0

    def sync_to_db(state: ProgressState) -> None:
        nonlocal last_db_sync
        now = time.monotonic()
        if now - last_db_sync < 0.8 and state.percent < 99:
            return
        last_db_sync = now

        async def _update() -> None:
            async with factory() as session:
                await update_job_progress(
                    session,
                    job_id,
                    percent=state.percent,
                    stage=state.stage,
                    partial_text=state.partial_text,
                )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(_update(), loop)
        except Exception:
            pass

    on_progress = make_callback(job_id, sync_to_db)

    try:
        result = await asyncio.to_thread(
            service.transcribe,
            file_path,
            preset_id=params["preset"],
            language=lang,
            task=params["task"],
            on_progress=on_progress,
        )

        async with factory() as session:
            transcription_id = None
            user_settings = await get_user_settings(session, params["user_id"])
            should_save = params["save"] and (
                user_settings.save_history if user_settings else True
            )
            segments_payload = (
                result.segments if params["response_format"] == "json" else None
            )
            if should_save:
                row = await save_transcription(
                    session,
                    user_id=params["user_id"],
                    text=result.text,
                    segments=segments_payload,
                    meta=result.meta,
                    source=params["source"],
                )
                transcription_id = row.id

            await complete_job(
                session,
                job_id,
                result_text=result.text,
                result_segments=segments_payload,
                result_meta=result.meta,
                transcription_id=transcription_id,
            )
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        async with factory() as session:
            await fail_job(session, job_id, str(exc))
    finally:
        clear_progress(job_id)
        file_path.unlink(missing_ok=True)


async def job_worker_loop() -> None:
    factory = get_session_factory()
    logger.info("Job worker started")

    while True:
        try:
            async with factory() as session:
                job = await claim_next_pending_job(session)

            if job is None:
                try:
                    await asyncio.wait_for(_wake_event.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
                _wake_event.clear()
                continue

            logger.info("Processing job %s (%.0fs audio)", job.id, job.duration_seconds or 0)
            await _process_job(
                job.id,
                Path(job.file_path),
                user_id=job.user_id,
                preset=job.preset,
                language=job.language,
                task=job.task,
                response_format=job.response_format,
                save=job.save,
                source=job.source,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker loop error")
            await asyncio.sleep(2)


def start_worker() -> None:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(job_worker_loop())


async def stop_worker() -> None:
    global _worker_task
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
