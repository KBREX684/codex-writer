import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def test_dashboard_json_output(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "测试书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--format", "json")
    run_cli("write", "--project-root", str(project), "--chapter", "1", "--format", "json")
    result = run_cli("dashboard", "--project-root", str(project), "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "project" in data["data"]
    assert "chapters" in data["data"]
    assert len(data["data"]["chapters"]) >= 1
    assert data["data"]["chapters"][0]["status"] == "accepted"


def test_dashboard_text_output(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "测试书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--format", "json")
    run_cli("write", "--project-root", str(project), "--chapter", "1", "--format", "json")
    result = run_cli("dashboard", "--project-root", str(project), "--format", "text")
    assert result.returncode == 0
    assert "测试书" in result.stdout
    assert "章节网格" in result.stdout
    assert "accepted" in result.stdout
