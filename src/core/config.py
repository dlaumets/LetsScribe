from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    device: str = "cpu"
    max_upload_mb: int = 500
    max_duration_hours: float = 4.0
    default_preset: str = "balanced"
    default_language: str = "ru"
    rate_limit_per_hour: int = 30
    queue_max_size: int = 5
    async_threshold_seconds: float = 900  # 15 min → background job
    whisper_cpu_threads: int = 0  # 0 = auto (all logical CPUs)
    whisper_num_workers: int = 1
    warmup_on_startup: bool = True
    # Override quality preset model on low-RAM VPS (e.g. small instead of medium)
    quality_model: str = ""

    database_url: str = "postgresql+asyncpg://transcribe:transcribe@localhost:5432/transcribe"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def max_duration_seconds(self) -> float:
        return self.max_duration_hours * 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
