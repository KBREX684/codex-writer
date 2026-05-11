import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def test_extract_writes_valid_extraction_result(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    chapter = project / "正文" / "第0001章-入局.md"
    chapter.parent.mkdir(exist_ok=True)
    chapter.write_text("萧衡获得青铜令，决定前往黑水城。", encoding="utf-8")
    result = run_cli("extract", "--project-root", str(project), "--chapter", "1", "--demo", "--format", "json")
    assert result.returncode == 0
    extraction = project / ".codex-writer" / "tmp" / "extraction_result.json"
    payload = json.loads(extraction.read_text(encoding="utf-8"))
    assert payload["chapter"] == 1
    assert isinstance(payload["accepted_events"], list)
