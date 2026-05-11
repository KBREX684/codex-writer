import json
import subprocess
import sys
from pathlib import Path


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def prepare_project(tmp_path: Path) -> Path:
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "测试书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--demo", "--format", "json")
    run_cli("write", "--project-root", str(project), "--chapter", "1", "--demo", "--format", "json")
    return project


def test_dashboard_json_output(tmp_path):
    project = prepare_project(tmp_path)
    result = run_cli("dashboard", "--project-root", str(project), "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "project" in data["data"]
    assert "chapters" in data["data"]
    assert len(data["data"]["chapters"]) >= 1
    assert data["data"]["chapters"][0]["status"] == "accepted"
    assert data["data"]["event_chain"]["total_events"] >= 1
    assert "foreshadowing" in data["data"]
    assert "entity_graph" in data["data"]


def test_dashboard_text_output_is_readable_chinese(tmp_path):
    project = prepare_project(tmp_path)
    result = run_cli("dashboard", "--project-root", str(project), "--format", "text")
    assert result.returncode == 0
    assert "测试书" in result.stdout
    assert "章节网格" in result.stdout
    assert "追读力" in result.stdout
    assert "accepted" in result.stdout


def test_dashboard_html_output(tmp_path):
    project = prepare_project(tmp_path)
    result = run_cli("dashboard", "--project-root", str(project), "--format", "html")
    assert result.returncode == 0
    output_path = project / ".codex-writer" / "dashboard" / "index.html"
    assert str(output_path) in result.stdout
    html = output_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in html
    assert "Codex Writer" in html
    assert "测试书" in html
    assert "最近章节网格" in html
    assert "事件链" in html
    assert "伏笔" in html
    assert "只读面板" in html


def test_dashboard_html_output_custom_path(tmp_path):
    project = prepare_project(tmp_path)
    result = run_cli(
        "dashboard",
        "--project-root",
        str(project),
        "--format",
        "html",
        "--output",
        "exports/dashboard.html",
    )
    assert result.returncode == 0
    output_path = project / "exports" / "dashboard.html"
    assert output_path.exists()
