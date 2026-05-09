import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def build_project(project):
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--format", "json")
    run_cli("write", "--project-root", str(project), "--chapter", "1", "--format", "json")


def test_status_and_events_health(tmp_path):
    project = tmp_path / "book"
    build_project(project)
    status = run_cli("status", "--project-root", str(project), "--format", "json")
    assert status.returncode == 0
    events = run_cli("events", "--project-root", str(project), "--health", "--format", "json")
    assert events.returncode == 0
    health = json.loads(events.stdout)
    assert health["data"]["consistent"] is True
    chapter_events = run_cli("events", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert chapter_events.returncode == 0
    payload = json.loads(chapter_events.stdout)
    assert "events" in payload["data"]
    assert isinstance(payload["data"]["events"], list)


def test_repair_projections_from_commit(tmp_path):
    project = tmp_path / "book"
    build_project(project)
    (project / ".codex-writer" / "state.json").unlink()
    result = run_cli("repair", "projections", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 0
    assert (project / ".codex-writer" / "state.json").exists()


def test_repair_logs_rebuilds_agent_runs(tmp_path):
    project = tmp_path / "book"
    build_project(project)
    result = run_cli("repair", "logs", "--project-root", str(project), "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["agent_runs_rebuilt"] >= 1
