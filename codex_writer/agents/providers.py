import json
import time
import urllib.error
import urllib.request
from typing import Protocol

from codex_writer.core.config import Settings, load_settings


OPENAI_COMPATIBLE = "openai_compatible"
CODEX_PROVIDER = "codex"
MOCK_PROVIDER = "mock"

# Retry configuration for transient HTTP errors (429, 5xx).
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0   # seconds; doubles on each attempt
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
# Extra attempts when the model returns an empty response (model-side fluke).
_MAX_EMPTY_RETRIES = 2


class ProviderConfigurationError(Exception):
    pass


class ModelProvider(Protocol):
    def generate(self, task: dict) -> dict:
        ...


class CodexProvider:
    def generate(self, task: dict) -> dict:
        return {"text": "", "json": {}, "raw": {}, "usage": {"provider": "codex"},
                "error": None, "warnings": [], "finish_reason": ""}


class MockProvider:
    def __init__(self, output: str = ""):
        self._output = output

    def generate(self, task: dict) -> dict:
        raw = self._output
        parsed = parse_json_content(raw)
        return {"text": raw, "json": parsed, "raw": raw, "usage": {"provider": "mock"},
                "error": None, "warnings": [], "finish_reason": "stop"}


def is_external_provider(provider: str) -> bool:
    return provider == OPENAI_COMPATIBLE


def provider_config_errors(
    provider: str,
    settings: Settings | None = None,
    model: str = "",
    base_url: str = "",
    api_key: str = "",
) -> list[dict]:
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
    effective_base_url = base_url or settings.openai_compatible_base_url
    effective_api_key = api_key or settings.openai_compatible_api_key
    route_model = model if model and model != "default" else ""
    effective_model = route_model or _effective_model(settings, "")
    if not effective_base_url:
        missing.append("CODEX_WRITER_OPENAI_COMPATIBLE_BASE_URL")
    if not effective_api_key:
        missing.append("CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY")
    if not effective_model:
        missing.append("CODEX_WRITER_OPENAI_COMPATIBLE_MODEL or route.model")
    if not missing:
        return []
    return [{
        "code": "PROVIDER_NOT_CONFIGURED",
        "message": "Missing provider configuration: " + ", ".join(missing),
        "blocking": True,
    }]


def create_provider(provider: str, model: str = "", settings: Settings | None = None,
                    mock_output: str | None = None, provider_options: dict | None = None) -> ModelProvider:
    if mock_output is not None:
        return MockProvider(mock_output)
    if provider in ("", CODEX_PROVIDER):
        return CodexProvider()
    if provider == OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(settings or load_settings(), model=model, options=provider_options or {})
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
    def __init__(self, settings: Settings | None = None, model: str = "", options: dict | None = None):
        self.settings = settings or load_settings()
        options = options or {}
        route_model = model if model and model != "default" else ""
        self.model = route_model or options.get("model") or _effective_model(self.settings, "")
        self.base_url = options.get("base_url") or self.settings.openai_compatible_base_url
        self.api_key = options.get("api_key") or self.settings.openai_compatible_api_key
        self.timeout_seconds = float(options.get("timeout") or self.settings.openai_compatible_timeout_seconds)
        self.max_tokens = int(options.get("max_tokens") or self.settings.openai_compatible_max_tokens or 0)
        errors = provider_config_errors(
            OPENAI_COMPATIBLE,
            self.settings,
            self.model,
            base_url=self.base_url,
            api_key=self.api_key,
        )
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
        max_tokens = int(task.get("max_tokens") or self.max_tokens or 0)
        if max_tokens > 0:
            body["max_tokens"] = max_tokens

        url = _chat_completions_url(self.base_url)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = ""
        delay = _RETRY_BASE_DELAY
        for attempt in range(1, _MAX_RETRIES + 1):
            request = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    raw_text = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                status = exc.code
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {status}: {detail}"
                if status in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                    # Respect Retry-After header when present (429).
                    # RFC 7231 allows either an integer (seconds) or an HTTP-date;
                    # we handle numeric values (int or float); HTTP-date values fall
                    # back to the exponential-backoff delay, which is safe.
                    retry_after = exc.headers.get("Retry-After")
                    try:
                        wait = float(retry_after) if retry_after else delay
                    except (TypeError, ValueError):
                        wait = delay
                    time.sleep(wait)
                    delay *= 2
                    continue
                return _provider_error(last_error)
            except OSError as exc:
                last_error = str(exc)
                if attempt < _MAX_RETRIES:
                    time.sleep(delay)
                    delay *= 2
                    continue
                return _provider_error(last_error)

            try:
                raw = json.loads(raw_text)
            except json.JSONDecodeError:
                return _provider_error("Provider returned invalid JSON")

            text, finish_reason = _extract_completion_text(raw)

            # Empty-output reroll: retry if model returned nothing (transient).
            if not text.strip() and attempt <= _MAX_EMPTY_RETRIES:
                time.sleep(delay)
                delay *= 2
                continue

            warnings = []
            if finish_reason == "length":
                warnings.append(
                    "模型输出因达到 max_tokens 上限而截断（finish_reason=length）；"
                    "请提高 CODEX_WRITER_OPENAI_COMPATIBLE_MAX_TOKENS 或检查章节长度设置"
                )

            return {
                "text": text,
                "json": parse_json_content(text),
                "raw": raw,
                "usage": raw.get("usage", {}),
                "error": None,
                "warnings": warnings,
                "finish_reason": finish_reason,
            }

        return _provider_error(last_error)


def _provider_error(message: str) -> dict:
    return {"text": "", "json": {}, "raw": {}, "usage": {}, "error": message,
            "warnings": [], "finish_reason": ""}


def _chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _extract_completion_text(raw: dict) -> tuple[str, str]:
    """Return (text, finish_reason) from an OpenAI-compatible response.

    Handles both the classic ``message.content: str`` format and the newer
    ``message.content: [{type: "text", text: "..."}]`` array format used by
    some providers (e.g. Anthropic-compatible endpoints).
    """
    choices = raw.get("choices") or []
    if not choices:
        return "", ""
    first = choices[0] or {}
    finish_reason = first.get("finish_reason") or ""
    message = first.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content, finish_reason
    # Array content format: [{type: "text", text: "..."}]
    if isinstance(content, list):
        parts = [
            part.get("text", "") for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "".join(parts), finish_reason
    # Legacy non-message format
    if isinstance(first.get("text"), str):
        return first["text"], finish_reason
    return "", finish_reason


def _effective_model(settings: Settings, model: str = "") -> str:
    if model and model != "default":
        return model
    return settings.openai_compatible_model
