from dataclasses import dataclass

CHAPTER_CHAR_LIMIT = 2000


@dataclass
class PrivacyPolicy:
    allow_external_models: bool = False
    allow_full_manuscript_upload: bool = False
    max_context_chapters_external: int = 2


def can_send_external(policy: PrivacyPolicy, input_kind: str, chars: int = 0) -> bool:
    if not policy.allow_external_models:
        return False
    if input_kind == "full_manuscript" and not policy.allow_full_manuscript_upload:
        return False
    char_limit = policy.max_context_chapters_external * CHAPTER_CHAR_LIMIT
    if chars > char_limit:
        return False
    return True


def load_privacy_from_env() -> PrivacyPolicy:
    import os
    try:
        max_ctx = int(os.environ.get("CODEX_WRITER_MAX_CONTEXT_CHAPTERS_EXTERNAL", "2"))
    except (ValueError, TypeError):
        max_ctx = 2
    return PrivacyPolicy(
        allow_external_models=os.environ.get("CODEX_WRITER_ALLOW_EXTERNAL_MODELS", "0") == "1",
        allow_full_manuscript_upload=os.environ.get("CODEX_WRITER_ALLOW_FULL_MANUSCRIPT", "0") == "1",
        max_context_chapters_external=max_ctx
    )
