import json
import sqlite3
import subprocess
import sys

from codex_writer.core.paths import chapter_md_path, commit_path


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def prepare_chapter(project):
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--format", "json")
    chapter = project / "正文" / "第0001章-入局.md"
    chapter.parent.mkdir(exist_ok=True)
    chapter.write_text("萧衡获得青铜令，决定前往黑水城。", encoding="utf-8")
    run_cli("review", "--project-root", str(project), "--chapter", "1", "--format", "json")
    run_cli("extract", "--project-root", str(project), "--chapter", "1", "--format", "json")


def test_commit_accepted_updates_state_summary_memory_index(tmp_path):
    project = tmp_path / "book"
    prepare_chapter(project)
    result = run_cli("commit", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 0
    commit = project / ".codex-writer" / "commits" / "第0001章提交.json"
    assert json.loads(commit.read_text(encoding="utf-8"))["meta"]["status"] == "accepted"
    assert (project / ".codex-writer" / "state.json").exists()
    assert (project / ".codex-writer" / "summaries" / "第0001章.md").exists()
    assert (project / ".codex-writer" / "index.sqlite").exists()
    assert (project / ".codex-writer" / "events" / "第0001章事件.json").exists()
    assert (project / ".codex-writer" / "logs" / "projections.jsonl").exists()


def test_commit_persists_projection_status_and_sqlite_read_models(tmp_path):
    project = tmp_path / "book"
    prepare_chapter(project)
    result = run_cli("commit", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 0

    commit = json.loads(commit_path(project, 1).read_text(encoding="utf-8"))
    assert commit["projection_status"] == {
        "state": "done",
        "summary": "done",
        "memory": "done",
        "index": "done",
    }

    with sqlite3.connect(project / ".codex-writer" / "index.sqlite") as conn:
        chapter_row = conn.execute(
            "SELECT chapter, status, word_count, summary, commit_path FROM chapters WHERE chapter = 1"
        ).fetchone()
        review_row = conn.execute(
            "SELECT chapter, issues_count, blocking_count, ai_flavor_count FROM reviews WHERE chapter = 1"
        ).fetchone()

    assert chapter_row is not None
    assert chapter_row[0] == 1
    assert chapter_row[1] == "accepted"
    assert chapter_row[2] > 0
    assert chapter_row[3]
    assert chapter_row[4].endswith("第0001章提交.json")
    assert review_row == (1, 0, 0, 0)


def test_state_word_count_uses_full_chapter_text_not_truncated_summary(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--format", "json")

    chapter_text = "第0001章 入局\n\n" + ("萧衡握紧青铜令，继续向黑水城前行。" * 30)
    chapter_path = chapter_md_path(project, 1, "入局")
    chapter_path.parent.mkdir(exist_ok=True)
    chapter_path.write_text(chapter_text, encoding="utf-8")

    run_cli("review", "--project-root", str(project), "--chapter", "1", "--format", "json")
    run_cli("extract", "--project-root", str(project), "--chapter", "1", "--format", "json")
    result = run_cli("commit", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 0

    state = json.loads((project / ".codex-writer" / "state.json").read_text(encoding="utf-8"))
    commit = json.loads(commit_path(project, 1).read_text(encoding="utf-8"))
    assert len(commit["summary_text"]) < len(chapter_text)
    assert state["chapters"]["1"]["word_count"] == len(chapter_text)


def test_events_are_written_to_json_and_sqlite(tmp_path):
    project = tmp_path / "book"
    prepare_chapter(project)
    extraction = project / ".codex-writer" / "tmp" / "extraction_result.json"
    payload = json.loads(extraction.read_text(encoding="utf-8"))
    payload["accepted_events"] = [
        {
            "event_id": "ch0001-plot-node",
            "chapter": 1,
            "event_type": "plot_node_covered",
            "subject": "入局",
            "payload": {"description": "萧衡前往黑水城"}
        }
    ]
    extraction.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    result = run_cli("commit", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 0
    event_file = project / ".codex-writer" / "events" / "第0001章事件.json"
    assert json.loads(event_file.read_text(encoding="utf-8"))[0]["event_id"] == "ch0001-plot-node"
    with sqlite3.connect(project / ".codex-writer" / "index.sqlite") as conn:
        count = conn.execute("SELECT COUNT(*) FROM events WHERE event_id = ?", ("ch0001-plot-node",)).fetchone()[0]
    assert count == 1


def test_rejected_commit_records_state(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    chapter = project / "正文" / "第0001章-入局.md"
    chapter.parent.mkdir(exist_ok=True)
    chapter.write_text("", encoding="utf-8")
    run_cli("review", "--project-root", str(project), "--chapter", "1", "--format", "json")
    run_cli("extract", "--project-root", str(project), "--chapter", "1", "--format", "json")
    result = run_cli("commit", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 3
    state = json.loads((project / ".codex-writer" / "state.json").read_text(encoding="utf-8"))
    assert state["chapters"]["1"]["status"] == "rejected"
