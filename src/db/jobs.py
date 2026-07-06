from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Job


async def create_job(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    file_path: str,
    duration_seconds: float,
    preset: str,
    language: str,
    task: str,
    response_format: str,
    save: bool,
    source: str,
) -> Job:
    job = Job(
        user_id=user_id,
        file_path=file_path,
        duration_seconds=duration_seconds,
        preset=preset,
        language=language,
        task=task,
        response_format=response_format,
        save=save,
        source=source,
        status="pending",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_job(session: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID) -> Job | None:
    result = await session.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def claim_next_pending_job(session: AsyncSession) -> Job | None:
    """Atomically claim the oldest pending job."""
    result = await session.execute(
        select(Job)
        .where(Job.status == "pending")
        .order_by(Job.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None

    job.status = "processing"
    job.started_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(job)
    return job


async def update_job_progress(
    session: AsyncSession,
    job_id: uuid.UUID,
    *,
    percent: float,
    stage: str,
    partial_text: str = "",
) -> None:
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(
            progress_percent=percent,
            progress_stage=stage,
            partial_text=partial_text or None,
        )
    )
    await session.commit()


async def complete_job(
    session: AsyncSession,
    job_id: uuid.UUID,
    *,
    result_text: str,
    result_segments: list | None,
    result_meta: dict,
    transcription_id: uuid.UUID | None,
) -> None:
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(
            status="completed",
            progress_percent=100.0,
            progress_stage="done",
            result_text=result_text,
            result_segments=result_segments,
            result_meta=result_meta,
            transcription_id=transcription_id,
            completed_at=datetime.now(timezone.utc),
            error_message=None,
        )
    )
    await session.commit()


async def fail_job(session: AsyncSession, job_id: uuid.UUID, error_message: str) -> None:
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(
            status="failed",
            error_message=error_message,
            completed_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()


async def cancel_job(
    session: AsyncSession,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[str, Job | None]:
    """Cancel a pending or processing job. Returns (result, job)."""
    from pathlib import Path

    from src.core.progress import request_cancel

    existing = await get_job(session, job_id, user_id)
    if existing is None:
        return "not_found", None
    if existing.status not in ("pending", "processing"):
        return "not_cancellable", existing

    pending_file = existing.file_path if existing.status == "pending" else None
    now = datetime.now(timezone.utc)

    result = await session.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.user_id == user_id,
            Job.status.in_(("pending", "processing")),
        )
        .values(
            status="cancelled",
            progress_stage="cancelled",
            error_message="Отменено пользователем",
            completed_at=now,
        )
        .returning(Job)
    )
    job = result.scalar_one_or_none()
    await session.commit()

    if job is None:
        refreshed = await get_job(session, job_id, user_id)
        return "not_cancellable", refreshed

    request_cancel(job_id)
    if pending_file:
        Path(pending_file).unlink(missing_ok=True)
    return "ok", job


async def list_jobs(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Job], int]:
    from sqlalchemy import func

    offset = (page - 1) * limit
    total_result = await session.execute(
        select(func.count()).select_from(Job).where(Job.user_id == user_id)
    )
    total = total_result.scalar_one()

    result = await session.execute(
        select(Job)
        .where(Job.user_id == user_id)
        .order_by(Job.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total
