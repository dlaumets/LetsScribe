from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    model: str
    compute_type: str
    description: str
    vad_filter: bool = True
    vad_parameters: dict = field(default_factory=dict)
    beam_size: int = 5
    best_of: int = 1
    condition_on_previous_text: bool = True


DEFAULT_VAD = {"min_silence_duration_ms": 500, "speech_pad_ms": 400}
FAST_VAD = {"min_silence_duration_ms": 650, "speech_pad_ms": 250}

PRESETS: dict[str, Preset] = {
    "fast": Preset(
        id="fast",
        label="Быстро",
        model="tiny",
        compute_type="int8",
        description="Максимальная скорость для коротких голосовых",
        vad_parameters={**FAST_VAD},
        beam_size=1,
        best_of=1,
        condition_on_previous_text=False,
    ),
    "balanced": Preset(
        id="balanced",
        label="Баланс",
        model="base",
        compute_type="int8",
        description="Оптимальный баланс скорости и качества на CPU",
        vad_parameters={**FAST_VAD},
        beam_size=1,
        best_of=1,
        condition_on_previous_text=False,
    ),
    "quality": Preset(
        id="quality",
        label="Качество",
        model="medium",
        compute_type="int8",
        description="Максимальное качество, медленнее на CPU",
        vad_parameters={"min_silence_duration_ms": 700, "speech_pad_ms": 300},
        beam_size=5,
        best_of=1,
        condition_on_previous_text=True,
    ),
}


def get_preset(preset_id: str) -> Preset:
    if preset_id not in PRESETS:
        raise ValueError(f"Unknown preset: {preset_id}. Available: {', '.join(PRESETS)}")
    return PRESETS[preset_id]


def list_presets() -> list[Preset]:
    return list(PRESETS.values())
