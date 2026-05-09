import subprocess
import sys


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def test_bad_argument_returns_2():
    result = run_cli("plan", "--chapter", "not-a-number", "--format", "json")
    assert result.returncode == 2


def test_privacy_block_returns_4(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "书", "--genre", "修仙", "--format", "json")
    result = run_cli("route-test", "--project-root", str(project), "--agent", "draft_agent", "--input-kind", "full_manuscript", "--provider", "openai_compatible", "--format", "json")
    assert result.returncode == 4
