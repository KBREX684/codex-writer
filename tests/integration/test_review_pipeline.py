import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def test_review_marks_empty_draft_blocking(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    chapter = project / "正文" / "第0001章-入局.md"
    chapter.parent.mkdir(exist_ok=True)
    chapter.write_text("", encoding="utf-8")
    result = run_cli("review", "--project-root", str(project), "--chapter", "1", "--format", "json")
    assert result.returncode == 3
    review = project / ".codex-writer" / "reviews" / "第0001章审查结果.json"
    payload = json.loads(review.read_text(encoding="utf-8"))
    assert payload["blocking_count"] >= 1
    issue = payload["issues"][0]
    assert set(["severity", "category", "location", "description", "evidence", "fix_hint", "blocking"]).issubset(issue)


def test_anti_ai_feedback_persists_issue(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    chapter = project / "正文" / "第0001章-入局.md"
    chapter.parent.mkdir(exist_ok=True)
    chapter.write_text("他深吸一口气。他知道，命运的齿轮已经开始转动。", encoding="utf-8")
    run_cli("review", "--project-root", str(project), "--chapter", "1", "--format", "json")
    feedback = project / ".codex-writer" / "story" / "反AI反馈.json"
    assert feedback.exists()
