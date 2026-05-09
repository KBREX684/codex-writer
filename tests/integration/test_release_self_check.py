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
