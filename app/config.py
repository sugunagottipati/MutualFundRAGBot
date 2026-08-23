"""Configuration loading and startup validation for Phase 0."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from app.constants import ALLOWED_DOMAIN, APPROVED_SOURCE_URLS, DEFAULT_REFUSAL_LINK


class ConfigError(ValueError):
    """Raised when environment configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    app_env: str
    api_host: str
    api_port: int
    llm_provider: str
    groq_api_key: str
    groq_model: str
    embedding_provider: str
    embedding_model: str
    vector_db_path: str
    sqlite_path: str
    allowed_domains: tuple[str, ...]
    allowed_source_urls: tuple[str, ...]
    default_refusal_link: str

    @classmethod
    def from_env(cls) -> "Settings":
        allowed_domains = _read_csv_env("ALLOWED_DOMAINS", default=ALLOWED_DOMAIN)
        allowed_source_urls = _read_csv_env(
            "ALLOWED_SOURCE_URLS",
            default=",".join(APPROVED_SOURCE_URLS),
        )

        return cls(
            app_env=_read_env("APP_ENV", "dev"),
            api_host=_read_env("API_HOST", "0.0.0.0"),
            api_port=int(_read_env("API_PORT", "8000")),
            llm_provider=_read_env("LLM_PROVIDER", "groq").lower(),
            groq_api_key=_read_env("GROQ_API_KEY"),
            groq_model=_read_env("GROQ_MODEL"),
            embedding_provider=_read_env("EMBEDDING_PROVIDER", "openai"),
            embedding_model=_read_env("EMBEDDING_MODEL", "text-embedding-3-small"),
            vector_db_path=_read_env("VECTOR_DB_PATH", "./data/chroma"),
            sqlite_path=_read_env("SQLITE_PATH", "./data/processed/app.db"),
            allowed_domains=allowed_domains,
            allowed_source_urls=allowed_source_urls,
            default_refusal_link=_read_env("DEFAULT_REFUSAL_LINK", DEFAULT_REFUSAL_LINK),
        )

    def validate(self) -> None:
        if self.llm_provider != "groq":
            raise ConfigError("LLM_PROVIDER must be set to 'groq' for this implementation.")

        if not self.groq_api_key.strip():
            raise ConfigError("GROQ_API_KEY is required.")

        if not self.groq_model.strip():
            raise ConfigError("GROQ_MODEL is required.")

        if ALLOWED_DOMAIN not in self.allowed_domains:
            raise ConfigError(f"ALLOWED_DOMAINS must include '{ALLOWED_DOMAIN}'.")

        approved_set = set(APPROVED_SOURCE_URLS)
        provided_set = set(self.allowed_source_urls)
        if provided_set != approved_set:
            missing = sorted(approved_set - provided_set)
            extra = sorted(provided_set - approved_set)
            raise ConfigError(
                "ALLOWED_SOURCE_URLS must match the approved 7-URL allowlist exactly. "
                f"Missing: {missing or 'none'}; Extra: {extra or 'none'}"
            )

        if self.default_refusal_link not in approved_set:
            raise ConfigError("DEFAULT_REFUSAL_LINK must be one of the approved allowlisted URLs.")


@lru_cache(maxsize=1)
def get_settings(validate: bool = True) -> Settings:
    settings = Settings.from_env()
    if validate:
        settings.validate()
    return settings


def _read_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def _read_csv_env(name: str, default: str | None = None) -> tuple[str, ...]:
    raw_value = _read_env(name, default)
    parsed = tuple(part.strip() for part in raw_value.split(",") if part.strip())
    if not parsed:
        raise ConfigError(f"{name} cannot be empty")
    return parsed
