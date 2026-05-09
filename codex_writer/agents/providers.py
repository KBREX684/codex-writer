from typing import Protocol


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
        import json
        raw = self._output
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
        return {"text": raw, "json": parsed, "raw": raw, "usage": {"provider": "mock"}, "error": None}
