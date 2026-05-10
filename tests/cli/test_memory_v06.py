import json
import subprocess
import sys
from pathlib import Path

from codex_writer.core.io import write_json_atomic
from codex_writer.memory.scratchpad import bootstrap


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "codex_writer.cli", *args], text=True, capture_output=True, check=False)


def test_memory_dump_and_update_entry(tmp_path: Path):
    project = tmp_path / "book"
    assert run_cli("init", "--project-root", str(project), "--title", "测试书", "--format", "json").returncode == 0
    learn = run_cli("learn", "主角出手前必须先有情绪债", "--tag", "节奏", "--project-root", str(project), "--format", "json")
    assert learn.returncode == 0
    entry_id = json.loads(learn.stdout)["data"]["id"]

    dump = run_cli("memory", "dump", "--project-root", str(project), "--format", "json")
    assert dump.returncode == 0
    dump_payload = json.loads(dump.stdout)
    assert dump_payload["data"]["episodic"][0]["id"] == entry_id

    update = run_cli(
        "memory", "update",
        "--project-root", str(project),
        "--id", entry_id,
        "--status", "archived",
        "--tag", "结构",
        "--format", "json",
    )
    assert update.returncode == 0
    updated = json.loads(update.stdout)["data"]["entry"]
    assert updated["status"] == "archived"
    assert updated["tag"] == "结构"

    stats = json.loads(run_cli("memory", "stats", "--project-root", str(project), "--format", "json").stdout)["data"]
    assert stats["episodic_archived"] == 1


def test_memory_conflicts_detects_semantic_fact_collision(tmp_path: Path):
    project = tmp_path / "book"
    (project / ".codex-writer").mkdir(parents=True)
    scratch = bootstrap(project)
    scratch["semantic"] = [
        {"id": "s1", "entity": "林烬", "field": "境界", "value": "练气三层", "status": "active", "source_chapter": 1},
        {"id": "s2", "entity": "林烬", "field": "境界", "value": "筑基", "status": "active", "source_chapter": 2},
    ]
    write_json_atomic(project / ".codex-writer" / "memory_scratchpad.json", scratch)

    result = run_cli("memory", "conflicts", "--project-root", str(project), "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["count"] == 1
    assert payload["data"]["results"][0]["entity"] == "林烬"
    assert payload["data"]["results"][0]["field"] == "境界"
