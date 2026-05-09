import json
import sqlite3
import subprocess
import sys


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def test_write_runs_one_chapter_pipeline(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--format", "json")
    result = run_cli("write", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert (project / "正文" / "第0001章-入局.md").exists()
    assert (project / ".codex-writer" / "commits" / "第0001章提交.json").exists()
    assert (project / ".codex-writer" / "logs" / "workflow.jsonl").exists()
    assert list((project / ".codex-writer" / "backups").glob("*/manifest.json"))


def test_write_pipeline_records_polish_step_and_agent_runs(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--format", "json")
    result = run_cli("write", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 0

    workflow = [
        json.loads(line)
        for line in (project / ".codex-writer" / "logs" / "workflow.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    transitions = {(entry["from"], entry["to"], entry["actor"]) for entry in workflow}
    assert ("reviewed", "polished", "polish_agent") in transitions
    assert ("polished", "extracted", "extract_agent") in transitions

    with sqlite3.connect(project / ".codex-writer" / "index.sqlite") as conn:
        agents = {
            row[0]
            for row in conn.execute("SELECT agent FROM agent_runs WHERE chapter = 1")
        }

    assert {"draft_agent", "review_agent", "polish_agent", "extract_agent"} <= agents


def test_write_without_chapter_brief_blocks(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    result = run_cli("write", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert any(error["code"] == "CHAPTER_BRIEF_MISSING" for error in payload["errors"])
    workflow = project / ".codex-writer" / "logs" / "workflow.jsonl"
    assert "blocked" in workflow.read_text(encoding="utf-8")
