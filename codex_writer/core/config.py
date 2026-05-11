import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    openai_compatible_base_url: str = ""
    openai_compatible_api_key: str = ""
    openai_compatible_model: str = ""
    openai_compatible_timeout_seconds: float = 60.0
    openai_compatible_max_tokens: int = 4096
    embed_base_url: str = ""
    embed_model: str = ""
    embed_api_key: str = ""
    rerank_base_url: str = ""
    rerank_model: str = ""
    rerank_api_key: str = ""
    allow_external_models: bool = False
    allow_full_manuscript: bool = False
    max_context_chapters_external: int = 2


def load_settings() -> Settings:
    return Settings(
        openai_compatible_base_url=os.environ.get("CODEX_WRITER_OPENAI_COMPATIBLE_BASE_URL", ""),
        openai_compatible_api_key=os.environ.get("CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY", ""),
        openai_compatible_model=os.environ.get("CODEX_WRITER_OPENAI_COMPATIBLE_MODEL", ""),
        openai_compatible_timeout_seconds=_env_float("CODEX_WRITER_OPENAI_COMPATIBLE_TIMEOUT_SECONDS", 60.0),
        openai_compatible_max_tokens=_env_int("CODEX_WRITER_OPENAI_COMPATIBLE_MAX_TOKENS", 4096),
        embed_base_url=os.environ.get("CODEX_WRITER_EMBED_BASE_URL", ""),
        embed_model=os.environ.get("CODEX_WRITER_EMBED_MODEL", ""),
        embed_api_key=os.environ.get("CODEX_WRITER_EMBED_API_KEY", ""),
        rerank_base_url=os.environ.get("CODEX_WRITER_RERANK_BASE_URL", ""),
        rerank_model=os.environ.get("CODEX_WRITER_RERANK_MODEL", ""),
        rerank_api_key=os.environ.get("CODEX_WRITER_RERANK_API_KEY", ""),
        allow_external_models=_env_bool("CODEX_WRITER_ALLOW_EXTERNAL_MODELS", False),
        allow_full_manuscript=_env_bool("CODEX_WRITER_ALLOW_FULL_MANUSCRIPT", False),
        max_context_chapters_external=_env_int("CODEX_WRITER_MAX_CONTEXT_CHAPTERS_EXTERNAL", 2),
    )
