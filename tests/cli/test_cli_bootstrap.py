import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "codex_writer.cli", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_help_lists_core_commands():
    result = run_cli("--help")
    assert result.returncode == 0
    assert "init" in result.stdout
    assert "doctor" in result.stdout
    assert "write" in result.stdout


def test_doctor_self_check_json_shape():
    result = run_cli("doctor", "--self-check", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "doctor"
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["errors"], list)
