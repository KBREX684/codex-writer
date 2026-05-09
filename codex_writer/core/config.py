import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    openai_compatible_base_url: str = ""
    openai_compatible_api_key: str = ""
    openai_compatible_model: str = ""
    allow_external_models: bool = False


def load_settings() -> Settings:
    return Settings(
        openai_compatible_base_url=os.environ.get("CODEX_WRITER_OPENAI_COMPATIBLE_BASE_URL", ""),
        openai_compatible_api_key=os.environ.get("CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY", ""),
        openai_compatible_model=os.environ.get("CODEX_WRITER_OPENAI_COMPATIBLE_MODEL", ""),
        allow_external_models=os.environ.get("CODEX_WRITER_ALLOW_EXTERNAL_MODELS", "0") == "1",
    )
