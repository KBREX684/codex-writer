import json
import sqlite3
import subprocess
import sys

from codex_writer.core.io import read_json, write_json_atomic
from codex_writer.core.paths import commit_path


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def build_project(project):
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--demo", "--format", "json")
    run_cli("write", "--project-root", str(project), "--chapter", "1", "--demo", "--format", "json")


def test_backup_list_shows_entry(tmp_path):
    project = tmp_path / "book"
    build_project(project)
    result = run_cli("backup", "list", "--project-root", str(project), "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data["data"]["backups"]) >= 1


def test_backup_verify_passes(tmp_path):
    project = tmp_path / "book"
    build_project(project)
    list_result = run_cli("backup", "list", "--project-root", str(project), "--format", "json")
    backups = json.loads(list_result.stdout)["data"]["backups"]
    bid = backups[0]["backup_id"]
    result = run_cli("backup", "verify", "--project-root", str(project), "--backup-id", bid, "--format", "json")
    assert result.returncode == 0


def test_status_focus_rag_reports_mode(tmp_path):
    project = tmp_path / "book"
    build_project(project)
    result = run_cli("status", "--project-root", str(project), "--focus", "rag", "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "rag_mode" in data["data"]


def test_plan_with_references_enrichment(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    result = run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "秘境探险", "--demo", "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["data"]["chapter"] == 1
    assert data["data"]["title"] == "秘境探险"


def test_plan_dry_run_does_not_write_file(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    result = run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--demo", "--dry-run", "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["data"]["dry_run"] is True
    brief = project / ".codex-writer" / "story" / "chapters" / "第0001章任务书.json"
    assert not brief.exists()


def test_learn_stores_author_note(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    result = run_cli("learn", "--project-root", str(project), "主角性格暴躁但讲义气", "--tag", "character", "--chapter", "3", "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["data"]["tag"] == "character"
    assert data["data"]["chapter"] == 3
    assert (project / ".codex-writer" / "memory_scratchpad.json").exists()


def test_learn_content_persisted_in_memory(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    run_cli("learn", "--project-root", str(project), "黑水城有三大势力", "--tag", "world_building", "--format", "json")
    result = run_cli("memory", "query", "--project-root", str(project), "--tag", "world_building", "--format", "json")
    data = json.loads(result.stdout)
    assert data["data"]["count"] >= 1


def test_memory_stats_shows_episodic_count(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--demo", "--format", "json")
    run_cli("write", "--project-root", str(project), "--chapter", "1", "--demo", "--format", "json")
    result = run_cli("memory", "stats", "--project-root", str(project), "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["data"]["episodic_total"] >= 1


def test_repair_projections_all_rebuilds(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--demo", "--format", "json")
    run_cli("write", "--project-root", str(project), "--chapter", "1", "--demo", "--format", "json")
    result = run_cli("repair", "projections", "--project-root", str(project), "--all", "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "repaired" in data["data"]


def test_repair_logs_rebuilds_sqlite_agent_runs(tmp_path):
    project = tmp_path / "book"
    build_project(project)
    db_path = project / ".codex-writer" / "index.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM agent_runs")
        conn.commit()

    result = run_cli("repair", "logs", "--project-root", str(project), "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["agent_runs_rebuilt"] >= 4

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0]
    assert count >= 4


def test_repair_projections_marks_commit_projection_done(tmp_path):
    project = tmp_path / "book"
    build_project(project)
    cp = commit_path(project, 1)
    commit = read_json(cp)
    commit["projection_status"] = {"state": "pending", "summary": "pending", "memory": "pending", "index": "pending"}
    write_json_atomic(cp, commit)

    result = run_cli("repair", "projections", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 0

    repaired = read_json(cp)
    assert repaired["projection_status"] == {
        "state": "done",
        "summary": "done",
        "memory": "done",
        "index": "done",
    }
