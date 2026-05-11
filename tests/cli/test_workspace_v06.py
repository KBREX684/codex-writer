import json
import os
import subprocess
import sys


def run_cli(*args, env=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "codex_writer.cli", *args],
        text=True,
        capture_output=True,
        check=False,
        env=merged_env,
    )


def test_use_where_resume_bind_active_project(tmp_path):
    home = tmp_path / "home"
    env = {"CODEX_WRITER_HOME": str(home)}
    project = tmp_path / "book"

    init = run_cli("init", "--project-root", str(project), "--title", "测试书", "--genre", "修仙", "--format", "json", env=env)
    assert init.returncode == 0

    use = run_cli("use", "--project-root", str(project), "--format", "json", env=env)
    assert use.returncode == 0
    use_payload = json.loads(use.stdout)
    assert use_payload["data"]["active_project_root"] == str(project.resolve())

    where = run_cli("where", "--format", "json", env=env)
    assert where.returncode == 0
    where_payload = json.loads(where.stdout)
    assert where_payload["data"]["active_project_root"] == str(project.resolve())
    assert where_payload["data"]["project"]["title"] == "测试书"

    resume = run_cli("resume", "--format", "json", env=env)
    assert resume.returncode == 0
    resume_payload = json.loads(resume.stdout)
    assert resume_payload["data"]["next_chapter"] == 1
    assert "plan" in resume_payload["data"]["suggested_commands"][0]


def test_resume_advances_after_accepted_chapter(tmp_path):
    home = tmp_path / "home"
    env = {"CODEX_WRITER_HOME": str(home)}
    project = tmp_path / "book"

    assert run_cli("init", "--project-root", str(project), "--title", "测试书", "--format", "json", env=env).returncode == 0
    assert run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--demo", "--format", "json", env=env).returncode == 0
    assert run_cli("write", "--project-root", str(project), "--chapter", "1", "--demo", "--format", "json", env=env).returncode == 0
    assert run_cli("use", "--project-root", str(project), "--format", "json", env=env).returncode == 0

    resume = run_cli("resume", "--format", "json", env=env)
    assert resume.returncode == 0
    payload = json.loads(resume.stdout)
    assert payload["data"]["current_chapter"] == 1
    assert payload["data"]["next_chapter"] == 2
