from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from src.core.config import get_settings
from src.core.presets import Preset, get_preset

if TYPE_CHECKING:
    from src.core.progress import ProgressCallback


@dataclass
class TranscriptionResult:
    text: str
    segments: list[dict]
    meta: dict


class TranscribeService:
    _instance: TranscribeService | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._settings = get_settings()
        self._model = None
        self._current_preset_id: str | None = None
        self._model_lock = threading.Lock()
        self._queue_lock = threading.Lock()
        self._queue_size = 0

    @classmethod
    def get_instance(cls) -> TranscribeService:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    @property
    def current_preset_id(self) -> str | None:
        return self._current_preset_id

    @property
    def queue_size(self) -> int:
        with self._queue_lock:
            return self._queue_size

    def _cpu_threads(self) -> int:
        threads = self._settings.whisper_cpu_threads
        if threads > 0:
            return threads
        return os.cpu_count() or 4

    def _ensure_model(self, preset: Preset):
        from faster_whisper import WhisperModel

        if self._current_preset_id == preset.id and self._model is not None:
            return self._model

        with self._model_lock:
            if self._current_preset_id == preset.id and self._model is not None:
                return self._model

            try:
                self._model = WhisperModel(
                    preset.model,
                    device=self._settings.device,
                    compute_type=preset.compute_type,
                    cpu_threads=self._cpu_threads(),
                    num_workers=self._settings.whisper_num_workers,
                )
            except OSError as exc:
                if getattr(exc, "errno", None) == -2:
                    raise RuntimeError(
                        f"Не удалось скачать модель «{preset.model}» (preset {preset.id}). "
                        "Проверьте DNS/интернет на сервере или выполните: "
                        "bash deploy/preload-models.sh quality"
                    ) from exc
                raise
            self._current_preset_id = preset.id
            return self._model

    def warmup(self, preset_id: str | None = None) -> None:
        preset = get_preset(preset_id or self._settings.default_preset)
        self._ensure_model(preset)

    def transcribe(
        self,
        audio_path: Path,
        *,
        preset_id: str = "balanced",
        language: str | None = "ru",
        task: str = "transcribe",
        on_progress: ProgressCallback | None = None,
    ) -> TranscriptionResult:
        from src.core.progress import ProgressState

        preset = get_preset(preset_id)
        started = time.perf_counter()

        with self._queue_lock:
            if self._queue_size >= self._settings.queue_max_size:
                raise RuntimeError("Queue is full, try again later")
            self._queue_size += 1

        try:
            if on_progress:
                on_progress(ProgressState(percent=2, stage="loading_model"))

            model = self._ensure_model(preset)

            if on_progress:
                on_progress(ProgressState(percent=8, stage="preparing"))

            segments_iter, info = model.transcribe(
                str(audio_path),
                language=language,
                task=task,
                beam_size=preset.beam_size,
                best_of=preset.best_of,
                condition_on_previous_text=preset.condition_on_previous_text,
                vad_filter=preset.vad_filter,
                vad_parameters=preset.vad_parameters,
                without_timestamps=True,
                temperature=0,
            )

            duration = info.duration or 0.0
            segments: list[dict] = []
            parts: list[str] = []
            for segment in segments_iter:
                parts.append(segment.text)
                segments.append(
                    {
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text,
                    }
                )
                if on_progress and duration > 0:
                    pct = min(98.0, 10.0 + (segment.end / duration) * 88.0)
                    on_progress(
                        ProgressState(
                            percent=pct,
                            stage="transcribing",
                            partial_text="".join(parts).strip(),
                            segments_done=len(segments),
                        )
                    )

            if on_progress:
                on_progress(ProgressState(percent=99, stage="finishing", partial_text="".join(parts).strip()))

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            text = "".join(parts).strip()
            meta = {
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "preset": preset.id,
                "processing_time_ms": elapsed_ms,
            }
            return TranscriptionResult(text=text, segments=segments, meta=meta)
        finally:
            with self._queue_lock:
                self._queue_size -= 1


def get_transcribe_service() -> TranscribeService:
    return TranscribeService.get_instance()
