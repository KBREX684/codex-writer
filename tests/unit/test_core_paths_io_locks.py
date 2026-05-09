import json
from pathlib import Path

import pytest

from codex_writer.core.errors import PathOutsideProject
from codex_writer.core.config import load_settings
from codex_writer.core.io import read_json, write_json_atomic
from codex_writer.core.locks import project_write_lock
from codex_writer.core.paths import resolve_in_project
from codex_writer.core.security import redact_secret, sanitize_filename


def test_resolve_in_project_rejects_parent_escape(tmp_path):
    with pytest.raises(PathOutsideProject):
        resolve_in_project(tmp_path, "../escape.json")


def test_write_json_atomic_roundtrip(tmp_path):
    target = tmp_path / ".codex-writer" / "state.json"
    write_json_atomic(target, {"chapter": 1, "title": "第一章"})
    assert read_json(target)["title"] == "第一章"
    assert not list(target.parent.glob("*.tmp"))


def test_project_write_lock_creates_runtime_lock(tmp_path):
    with project_write_lock(tmp_path):
        assert (tmp_path / ".codex-writer" / "runtime.lock").exists()


def test_security_sanitizes_filename_and_redacts_secret():
    assert ".." not in sanitize_filename("../坏:name?.json")
    assert redact_secret("sk-1234567890") == "sk-***"


def test_load_settings_reads_codex_writer_env(monkeypatch):
    monkeypatch.setenv("CODEX_WRITER_OPENAI_COMPATIBLE_MODEL", "writer-large")
    settings = load_settings()
    assert settings.openai_compatible_model == "writer-large"
