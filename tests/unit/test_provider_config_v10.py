from codex_writer.agents.provider_config import (
    resolve_openai_compatible_options,
    save_provider_config,
)
from codex_writer.core.paths import provider_config_path


def test_provider_config_priority_project_then_env_then_cli(tmp_path, monkeypatch):
    project = tmp_path / "book"
    save_provider_config(
        project,
        preset="custom",
        base_url="http://project.local/v1",
        model="project-model",
        timeout=15,
        max_tokens=2048,
    )

    monkeypatch.setenv("CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY", "sk-unit-test")
    project_options = resolve_openai_compatible_options(project)
    assert project_options["base_url"] == "http://project.local/v1"
    assert project_options["model"] == "project-model"
    assert project_options["timeout"] == 15
    assert project_options["max_tokens"] == 2048

    monkeypatch.setenv("CODEX_WRITER_OPENAI_COMPATIBLE_BASE_URL", "http://env.local/v1")
    monkeypatch.setenv("CODEX_WRITER_OPENAI_COMPATIBLE_MODEL", "env-model")
    monkeypatch.setenv("CODEX_WRITER_OPENAI_COMPATIBLE_TIMEOUT_SECONDS", "22")
    monkeypatch.setenv("CODEX_WRITER_OPENAI_COMPATIBLE_MAX_TOKENS", "333")
    env_options = resolve_openai_compatible_options(project)
    assert env_options["base_url"] == "http://env.local/v1"
    assert env_options["model"] == "env-model"
    assert env_options["timeout"] == 22
    assert env_options["max_tokens"] == 333

    cli_options = resolve_openai_compatible_options(
        project,
        cli_overrides={
            "base_url": "http://cli.local/v1",
            "model": "cli-model",
            "timeout": 7,
            "max_tokens": 99,
        },
    )
    assert cli_options["base_url"] == "http://cli.local/v1"
    assert cli_options["model"] == "cli-model"
    assert cli_options["timeout"] == 7
    assert cli_options["max_tokens"] == 99


def test_provider_config_file_never_stores_api_key(tmp_path):
    project = tmp_path / "book"
    save_provider_config(
        project,
        preset="custom",
        base_url="http://project.local/v1",
        model="project-model",
    )
    raw = provider_config_path(project).read_text(encoding="utf-8").lower()
    assert "api_key" not in raw
    assert "sk-" not in raw
