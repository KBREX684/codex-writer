import json
import urllib.error
import urllib.request
from typing import Protocol

from codex_writer.core.config import Settings, load_settings


OPENAI_COMPATIBLE = "openai_compatible"
CODEX_PROVIDER = "codex"
MOCK_PROVIDER = "mock"


class ProviderConfigurationError(Exception):
    pass


class ModelProvider(Protocol):
    def generate(self, task: dict) -> dict:
        ...


class CodexProvider:
    def generate(self, task: dict) -> dict:
        return {"text": "", "json": {}, "raw": {}, "usage": {"provider": "codex"}, "error": None}


class MockProvider:
    def __init__(self, output: str = ""):
        self._output = output

    def generate(self, task: dict) -> dict:
        raw = self._output
        parsed = parse_json_content(raw)
        return {"text": raw, "json": parsed, "raw": raw, "usage": {"provider": "mock"}, "error": None}


def is_external_provider(provider: str) -> bool:
    return provider == OPENAI_COMPATIBLE


def provider_config_errors(provider: str, settings: Settings | None = None, model: str = "") -> list[dict]:
    settings = settings or load_settings()
    if provider in ("", CODEX_PROVIDER, MOCK_PROVIDER):
        return []
    if provider != OPENAI_COMPATIBLE:
        return [{
            "code": "UNSUPPORTED_PROVIDER",
            "message": f"Unsupported provider for production mode: {provider}",
            "blocking": True,
        }]

    missing = []
    if not settings.openai_compatible_base_url:
        missing.append("CODEX_WRITER_OPENAI_COMPATIBLE_BASE_URL")
    if not settings.openai_compatible_api_key:
        missing.append("CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY")
    if not _effective_model(settings, model):
        missing.append("CODEX_WRITER_OPENAI_COMPATIBLE_MODEL or route.model")
    if not missing:
        return []
    return [{
        "code": "PROVIDER_NOT_CONFIGURED",
        "message": "Missing provider configuration: " + ", ".join(missing),
        "blocking": True,
    }]


def create_provider(provider: str, model: str = "", settings: Settings | None = None,
                    mock_output: str | None = None) -> ModelProvider:
    if mock_output is not None:
        return MockProvider(mock_output)
    if provider in ("", CODEX_PROVIDER):
        return CodexProvider()
    if provider == OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(settings or load_settings(), model=model)
    raise ProviderConfigurationError(f"Unsupported provider: {provider}")


def parse_json_content(content: str) -> dict:
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class OpenAICompatibleProvider:
    def __init__(self, settings: Settings | None = None, model: str = ""):
        self.settings = settings or load_settings()
        self.model = _effective_model(self.settings, model)
        errors = provider_config_errors(OPENAI_COMPATIBLE, self.settings, self.model)
        if errors:
            raise ProviderConfigurationError(errors[0]["message"])

    def generate(self, task: dict) -> dict:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": task.get("system_prompt", "")},
                {"role": "user", "content": task.get("task_prompt", "")},
            ],
            "temperature": task.get("temperature", 0.7),
        }
        max_tokens = int(task.get("max_tokens") or self.settings.openai_compatible_max_tokens or 0)
        if max_tokens > 0:
            body["max_tokens"] = max_tokens

        request = urllib.request.Request(
            _chat_completions_url(self.settings.openai_compatible_base_url),
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.openai_compatible_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.settings.openai_compatible_timeout_seconds,
            ) as response:
                raw_text = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return _provider_error(f"HTTP {exc.code}: {detail}")
        except OSError as exc:
            return _provider_error(str(exc))

        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError:
            return _provider_error("Provider returned invalid JSON")

        text = _extract_completion_text(raw)
        return {
            "text": text,
            "json": parse_json_content(text),
            "raw": raw,
            "usage": raw.get("usage", {}),
            "error": None,
        }


def _provider_error(message: str) -> dict:
    return {"text": "", "json": {}, "raw": {}, "usage": {}, "error": message}


def _chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _extract_completion_text(raw: dict) -> str:
    choices = raw.get("choices") or []
    if not choices:
        return ""
    first = choices[0] or {}
    message = first.get("message") or {}
    if isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(first.get("text"), str):
        return first["text"]
    return ""


def _effective_model(settings: Settings, model: str = "") -> str:
    if model and model != "default":
        return model
    return settings.openai_compatible_model
