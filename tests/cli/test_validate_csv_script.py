import json
import subprocess
import sys


def test_validate_csv_script_outputs_json_without_runtime_side_effects(tmp_path):
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    (csv_dir / "写作技法.csv").write_text(
        "id,category,tag,content\n"
        "tech-001,节奏,转折,用明确行动承接情绪变化\n",
        encoding="utf-8",
    )
    log_dir = tmp_path / ".codex-writer"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_csv.py",
            "--references-dir", str(csv_dir),
            "--format", "json",
            "--no-log",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["csv_count"] == 1
    assert payload["error_count"] == 0
    assert not log_dir.exists()
