import json
import subprocess
import sys
from pathlib import Path

from codex_writer.core.io import read_json


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def test_genres_list_contains_six_core_webnovel_templates():
    result = run_cli("genres", "list", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    names = {item["name"] for item in payload["data"]["templates"]}
    assert {"玄幻", "都市脑洞", "规则怪谈", "狗血言情", "古言", "现实题材"} <= names


def test_genres_show_returns_codex_writer_template_contract():
    result = run_cli("genres", "show", "--genre", "玄幻", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    template = payload["data"]["template"]
    assert template["name"] == "玄幻"
    assert template["routing_hints"]["draft_agent"] == "draft_agent"
    assert template["review_focus"]


def test_plan_applies_matching_genre_template(tmp_path: Path):
    project = tmp_path / "book"
    assert run_cli("init", "--project-root", str(project), "--title", "测试书", "--genre", "玄幻", "--format", "json").returncode == 0

    result = run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "入局", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["suggestions"]["genre_template"] == "玄幻"

    brief = read_json(project / ".codex-writer" / "story" / "chapters" / "第0001章任务书.json")
    assert any("爽点" in item or "升级" in item for item in brief["style_guidance"])
    saved_template = read_json(project / ".codex-writer" / "story" / "题材模板.json")
    assert saved_template["name"] == "玄幻"
