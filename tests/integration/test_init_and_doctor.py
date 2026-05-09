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


def test_init_creates_project_structure(tmp_path):
    project = tmp_path / "凡人资本论"
    result = run_cli("init", "--project-root", str(project), "--title", "凡人资本论", "--genre", "修仙", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert (project / ".codex-writer" / "project.json").exists()
    assert (project / ".codex-writer" / "story" / "故事合同.json").exists()
    assert (project / ".codex-writer" / "agents" / "子Agent路由.json").exists()
    assert (project / ".codex-writer" / "story" / "volumes" / "第001卷合同.json").exists()
    assert (project / ".codex-writer" / "agents" / "运行记录").is_dir()
    assert (project / ".codex-writer" / "events").is_dir()
    assert (project / ".codex-writer" / "reviews").is_dir()
    assert (project / ".codex-writer" / "commits").is_dir()
    assert (project / ".codex-writer" / "summaries").is_dir()
    assert (project / ".codex-writer" / "backups").is_dir()
    assert (project / ".codex-writer" / "migrations" / "applied.json").exists()


def test_doctor_strict_reports_missing_chapter_brief(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "玄幻", "--format", "json")
    result = run_cli("doctor", "--project-root", str(project), "--strict", "--chapter", "1", "--format", "json")
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert any(error["code"] == "CHAPTER_BRIEF_MISSING" for error in payload["errors"])


def test_doctor_strict_reports_placeholder(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "玄幻", "--format", "json")
    setting = project / "设定" / "人物.md"
    setting.write_text("主角：[待补充]", encoding="utf-8")
    result = run_cli("doctor", "--project-root", str(project), "--strict", "--format", "json")
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert any(error["code"] == "PLACEHOLDER_FOUND" for error in payload["errors"])
