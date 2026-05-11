import json
import subprocess
import sys
from pathlib import Path


def test_self_check_passes():
    result = subprocess.run(
        [sys.executable, "-m", "codex_writer.cli", "doctor", "--self-check", "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


def test_python_version_contract_matches_supported_runtime():
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.10"' in pyproject_text


def test_release_version_and_plugin_manifest_match_v07_surface():
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")
    plugin = json.loads(Path(".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    expected_commands = {
        "init", "doctor", "plan", "context", "write", "review", "extract", "commit",
        "query", "status", "events", "migrate", "backup", "restore", "repair",
        "agents", "route-test", "run-agent", "preflight", "references", "memory",
        "reading-power", "learn", "dashboard", "genres", "use", "where", "resume",
    }

    assert 'version = "0.7.0"' in pyproject_text
    assert plugin["version"] == "0.7.0"
    assert plugin["skills"] == "./skills/"
    assert "entry" not in plugin
    assert "commands" not in plugin
    assert isinstance(plugin["interface"]["defaultPrompt"], list)
    assert 1 <= len(plugin["interface"]["defaultPrompt"]) <= 3

    from codex_writer import __version__
    assert __version__ == "0.7.0"

    help_text = subprocess.run(
        [sys.executable, "-m", "codex_writer.cli", "--help"],
        text=True,
        capture_output=True,
        check=False,
    ).stdout
    assert expected_commands <= set(help_text.replace(",", " ").split())
