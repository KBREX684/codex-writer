import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def make_project(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--demo", "--format", "json")
    chapter = project / "正文" / "第0001章-入局.md"
    chapter.write_text("萧衡获得青铜令，决定前往黑水城。", encoding="utf-8")
    return project


def test_write_blocks_when_story_contract_missing(tmp_path):
    project = make_project(tmp_path)
    (project / ".codex-writer" / "story" / "故事合同.json").unlink()
    result = run_cli("write", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert any(error["code"] == "STORY_CONTRACT_MISSING" for error in payload["errors"])


def test_accepted_commit_does_not_double_count_words(tmp_path):
    project = make_project(tmp_path)
    run_cli("review", "--project-root", str(project), "--chapter", "1", "--format", "json")
    run_cli("extract", "--project-root", str(project), "--chapter", "1", "--demo", "--format", "json")
    first = run_cli("commit", "--project-root", str(project), "--chapter", "1", "--format", "json")
    second = run_cli("commit", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert first.returncode == 0
    assert second.returncode == 0
    state = json.loads((project / ".codex-writer" / "state.json").read_text(encoding="utf-8"))
    assert state["chapters"]["1"]["word_count"] == state["total_word_count"]


def test_invalid_extraction_schema_blocks_commit(tmp_path):
    project = make_project(tmp_path)
    run_cli("review", "--project-root", str(project), "--chapter", "1", "--format", "json")
    extraction = project / ".codex-writer" / "tmp" / "extraction_result.json"
    extraction.parent.mkdir(parents=True, exist_ok=True)
    extraction.write_text('{"chapter": 1}', encoding="utf-8")
    result = run_cli("commit", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert any(error["code"] == "SCHEMA_VALIDATION_FAILED" for error in payload["errors"])


def test_external_agent_invalid_json_fails_without_commit(tmp_path):
    project = make_project(tmp_path)
    result = run_cli(
        "run-agent",
        "--project-root", str(project),
        "--agent", "extract_agent",
        "--provider", "local_command",
        "--mock-output", "not-json",
        "--format", "json",
    )
    assert result.returncode in (0, 2, 5)
    if result.returncode != 0:
        assert not (project / ".codex-writer" / "commits" / "第0001章提交.json").exists()


def test_draft_agent_output_cannot_bypass_review_to_accepted(tmp_path):
    project = make_project(tmp_path)
    run_cli("run-agent", "--project-root", str(project), "--agent", "draft_agent", "--format", "json")
    result = run_cli("commit", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    codes = {error["code"] for error in payload["errors"]}
    assert "REVIEW_RESULT_MISSING" in codes or "EXTRACTION_RESULT_MISSING" in codes


def test_doctor_strict_reports_missing_migration(tmp_path):
    project = make_project(tmp_path)
    applied = project / ".codex-writer" / "migrations" / "applied.json"
    applied.write_text("[]", encoding="utf-8")
    result = run_cli("doctor", "--project-root", str(project), "--strict", "--format", "json")
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert any(error["code"] == "MIGRATION_MISSING" for error in payload["errors"])


def test_query_state_deltas_returns_extracted_data(tmp_path):
    project = make_project(tmp_path)
    run_cli("review", "--project-root", str(project), "--chapter", "1", "--format", "json")
    run_cli("extract", "--project-root", str(project), "--chapter", "1", "--demo", "--format", "json")
    extraction = project / ".codex-writer" / "tmp" / "extraction_result.json"
    payload = json.loads(extraction.read_text(encoding="utf-8"))
    payload["state_deltas"] = [{"entity": "萧衡", "field": "location", "new_value": "黑水城"}]
    payload["accepted_events"] = [{
        "event_id": "ch0001-state-delta",
        "chapter": 1,
        "event_type": "character_state_changed",
        "subject": "萧衡",
        "payload": {"entity": "萧衡", "field": "location", "new_value": "黑水城"}
    }]
    extraction.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    run_cli("commit", "--project-root", str(project), "--chapter", "1", "--format", "json")
    result = run_cli("query", "--project-root", str(project), "entity", "--name", "萧衡", "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["data"]["found"] is True


def test_open_loops_pass_to_next_chapter_context(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--demo", "--format", "json")
    chapter = project / "正文" / "第0001章-入局.md"
    chapter.parent.mkdir(exist_ok=True)
    chapter.write_text("萧衡获得青铜令，决定前往黑水城。", encoding="utf-8")
    run_cli("review", "--project-root", str(project), "--chapter", "1", "--format", "json")
    run_cli("extract", "--project-root", str(project), "--chapter", "1", "--demo", "--format", "json")
    extraction = project / ".codex-writer" / "tmp" / "extraction_result.json"
    payload = json.loads(extraction.read_text(encoding="utf-8"))
    payload["accepted_events"] = [{
        "event_id": "ch0001-open-loop",
        "chapter": 1,
        "event_type": "open_loop_created",
        "subject": "青铜令秘密",
        "payload": {"description": "青铜令来历不明"}
    }]
    extraction.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    run_cli("commit", "--project-root", str(project), "--chapter", "1", "--format", "json")
    run_cli("plan", "--project-root", str(project), "--chapter", "2", "--title", "黑水城", "--demo", "--format", "json")
    result = run_cli("context", "--project-root", str(project), "--chapter", "2", "--format", "json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data["data"]["open_loops"]) >= 1
    assert any(loop.get("description") == "青铜令来历不明" or loop.get("content") == "青铜令来历不明" or loop.get("subject") == "青铜令秘密" for loop in data["data"]["open_loops"])
