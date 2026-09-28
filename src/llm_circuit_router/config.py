"""Environment-backed configuration for the router.

Settings are resolved lazily through :func:`get_settings`, so importing any
pipeline module never requires a populated ``.env`` file. Credentials are only
demanded at the moment a stage actually needs them.

Secret fields are masked in ``repr()``/``str()`` because settings objects tend
to end up in log lines and tracebacks.
"""

from __future__ import annotations

from functools import lru_cache
from typing import ClassVar, Tuple

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.llm_circuit_router.security import REDACTED


class Settings(BaseSettings):
    """Provider credentials and base URLs read from the environment/``.env``."""

    NARA_API_KEY: str
    NARA_BASE_URL: str

    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str

    BENCHMARK_API_KEY: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Field names that must never be rendered by __repr__/__str__.
    SECRET_FIELD_NAMES: ClassVar[Tuple[str, ...]] = (
        "NARA_API_KEY",
        "OPENROUTER_API_KEY",
        "BENCHMARK_API_KEY",
    )

    def __repr__(self) -> str:
        rendered = (
            f"{name}={REDACTED!r}"
            if name in self.SECRET_FIELD_NAMES
            else f"{name}={getattr(self, name)!r}"
            for name in type(self).model_fields
        )
        return f"{type(self).__name__}({', '.join(rendered)})"

    # ``str()`` has its own pydantic implementation that would otherwise leak.
    __str__ = __repr__


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton, loading ``.env`` on first use."""
    return Settings()
