from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    base_url: str
    database_url: str
    inactivity_days: int
    code_length: int


def load_settings() -> Settings:
    base_url = os.getenv("BASE_URL", "").strip().rstrip("/")
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://shorten:shorten@db:5432/shorten"
    )
    inactivity_days = int(os.getenv("INACTIVITY_DAYS", "30"))
    code_length = int(os.getenv("CODE_LENGTH", "6"))
    return Settings(
        base_url=base_url,
        database_url=database_url,
        inactivity_days=inactivity_days,
        code_length=code_length,
    )
