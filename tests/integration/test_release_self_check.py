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


def test_release_version_and_plugin_commands_match_v05_surface():
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")
    plugin = json.loads(Path(".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    expected_commands = {
        "init", "doctor", "plan", "context", "write", "review", "extract", "commit",
        "query", "status", "events", "migrate", "backup", "restore", "repair",
        "agents", "route-test", "run-agent", "preflight", "references", "memory",
        "reading-power", "learn", "dashboard",
    }

    assert 'version = "0.5.0"' in pyproject_text
    assert plugin["version"] == "0.5.0"
    assert expected_commands <= set(plugin["commands"])

    from codex_writer import __version__
    assert __version__ == "0.5.0"
