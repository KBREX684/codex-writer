import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from codex_writer.core.paths import chapter_brief_path, chapter_md_path, commit_path, state_path


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


class SequenceChatHandler(BaseHTTPRequestHandler):
    responses = []
    requests = []

    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self.__class__.requests.append({
            "path": self.path,
            "authorization": self.headers.get("authorization", ""),
            "body": json.loads(body),
        })
        content = self.__class__.responses.pop(0) if self.__class__.responses else ""
        payload = {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        return


def start_chat_server(responses):
    SequenceChatHandler.responses = list(responses)
    SequenceChatHandler.requests = []
    server = HTTPServer(("127.0.0.1", 0), SequenceChatHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    return server, base_url, SequenceChatHandler.requests


def make_project(tmp_path):
    project = tmp_path / "book"
    result = run_cli("init", "--project-root", str(project), "--title", "Book", "--genre", "xianxia", "--format", "json")
    assert result.returncode == 0
    return project


def seed_foundation(project):
    story_path = project / ".codex-writer" / "story" / "故事合同.json"
    story = json.loads(story_path.read_text(encoding="utf-8"))
    story["core"] = {
        "one_sentence_pitch": "A disgraced cultivator rebuilds his path through a concrete revenge vow.",
        "core_tone": "sharp, escalating, contract-first xianxia",
        "main_conflict": "Xiao Heng must expose the sect conspiracy before his stolen foundation collapses.",
        "reader_promise": ["clear cultivation gains", "stable power rules", "escalating enemies"],
    }
    story["hard_rules"] = ["No realm jump without cost."]
    story["world_rules"] = ["Spirit roots determine safe qi intake and backlash risk."]
    story["main_characters"] = [{"name": "Xiao Heng", "role": "protagonist", "motivation": "restore his stolen foundation"}]
    story["style_rules"] = ["End each chapter on a new threat, cost, or resource."]
    story["forbidden_patterns"] = ["Do not solve conflicts with unexplained hidden masters."]
    story_path.write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")

    volume_path = project / ".codex-writer" / "story" / "volumes" / "第001卷合同.json"
    volume = json.loads(volume_path.read_text(encoding="utf-8"))
    volume.update({
        "title": "Blackwater Awakening",
        "goal": "Xiao Heng survives the opening conspiracy and claims the bronze token.",
        "key_milestones": ["public humiliation", "bronze token discovery", "sealed gate opens"],
        "characters_introduced": ["Xiao Heng", "Blackwater Elder"],
        "ending_hook": "The sect learns the stolen foundation is still alive.",
    })
    volume_path.write_text(json.dumps(volume, ensure_ascii=False, indent=2), encoding="utf-8")

    (project / "设定" / "世界观.md").write_text("灵根、灵脉、境界反噬构成修行物理。", encoding="utf-8")
    (project / "设定" / "人物卡.md").write_text("萧衡：被夺根基后以复仇和自证为动机。", encoding="utf-8")
    (project / "大纲" / "总纲.md").write_text("全书围绕夺回根基、揭开宗门旧案、重定仙途规则推进。", encoding="utf-8")
    (project / "大纲" / "第001卷纲.md").write_text("第一卷完成弱势开局、资源发现、第一轮敌人压迫。", encoding="utf-8")


def env_with_key():
    return {
        "CODEX_WRITER_ALLOW_EXTERNAL_MODELS": "1",
        "CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY": "sk-v1-test-secret",
        "CODEX_WRITER_MAX_CONTEXT_CHAPTERS_EXTERNAL": "50",
    }


def configure_provider(project, base_url, model="writer-v1"):
    result = run_cli(
        "provider",
        "--project-root", str(project),
        "configure",
        "--preset", "custom",
        "--base-url", base_url,
        "--model", model,
        "--timeout", "15",
        "--max-tokens", "2048",
        "--format", "json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def brief_json(chapter, title):
    return json.dumps({
        "meta": {"schema_version": "codex-writer/chapter-brief/v1"},
        "chapter": chapter,
        "title": title,
        "goal": f"Chapter {chapter} goal.",
        "must_cover_nodes": [],
        "forbidden_zones": [],
        "key_entities": ["Xiao Heng"],
        "context_summary": "The journey continues.",
        "character_motivation": [],
        "style_guidance": [],
        "ending_hook": "A new clue appears.",
        "anti_ai_reminders": [],
    })


def draft_text(chapter):
    return (
        f"# Chapter {chapter:04d}\n\n"
        f"Xiao Heng obtained a bronze token in chapter {chapter} and pushed through the sealed gate.\n\n"
        "\"Open it,\" he said, and the watching crowd fell silent as the old seal cracked."
    )


def extraction_json(chapter):
    return json.dumps({
        "meta": {"schema_version": "codex-writer/extraction-result/v1"},
        "chapter": chapter,
        "covered_nodes": [],
        "missed_nodes": [],
        "pending_disambiguation": [],
        "state_deltas": [],
        "entity_deltas": [{"entity": "Xiao Heng", "chapter": chapter, "mentioned": True}],
        "entities_appeared": [{"entity": "Xiao Heng", "count": 1, "first_position": 0}],
        "accepted_events": [{
            "event_id": f"ch{chapter:04d}-external-extract",
            "chapter": chapter,
            "event_type": "external_extraction",
            "subject": "Xiao Heng",
            "payload": {"source": "mock-provider"},
        }],
        "scenes": [{"index": 1, "text_preview": "Xiao Heng obtained a bronze token"}],
        "summary_text": f"Chapter {chapter} summary.",
        "dominant_thread": "main",
    })


def test_provider_configure_writes_non_secret_project_config(tmp_path):
    project = make_project(tmp_path)
    payload = configure_provider(project, "http://127.0.0.1:9999/v1")

    config_path = project / ".codex-writer" / "agents" / "模型供应商.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    raw = config_path.read_text(encoding="utf-8")

    assert payload["data"]["provider"]["preset"] == "custom"
    assert config["provider"]["base_url"] == "http://127.0.0.1:9999/v1"
    assert config["provider"]["model"] == "writer-v1"
    assert "api_key" not in raw.lower()
    assert "sk-" not in raw


def test_provider_status_and_test_redact_api_key(tmp_path):
    project = make_project(tmp_path)
    server, base_url, requests = start_chat_server(["OK"])
    try:
        configure_provider(project, base_url)
        env = env_with_key()
        status = run_cli("provider", "--project-root", str(project), "status", "--format", "json", env=env)
        test = run_cli("provider", "--project-root", str(project), "test", "--format", "json", env=env)
    finally:
        server.shutdown()

    assert status.returncode == 0
    status_payload = json.loads(status.stdout)
    assert status_payload["data"]["provider"]["api_key_present"] is True
    assert "sk-v1-test-secret" not in status.stdout

    assert test.returncode == 0
    assert requests[0]["authorization"] == "Bearer sk-v1-test-secret"
    assert "sk-v1-test-secret" not in test.stdout


def test_preflight_reports_blank_foundation_after_init(tmp_path):
    project = make_project(tmp_path)

    result = run_cli("preflight", "--project-root", str(project), "--chapter", "1", "--format", "json")

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["data"]["foundation"]["ready"] is False
    assert any(warning["code"] == "FOUNDATION_INCOMPLETE" for warning in payload["data"]["warnings"])


def test_plan_chapter_one_blocks_when_foundation_blank(tmp_path):
    project = make_project(tmp_path)
    server, base_url, requests = start_chat_server([brief_json(1, "Entry")])
    configure_provider(project, base_url)

    try:
        result = run_cli(
            "plan",
            "--project-root", str(project),
            "--chapter", "1",
            "--title", "Entry",
            "--format", "json",
            env=env_with_key(),
        )
    finally:
        server.shutdown()

    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any(error["code"] == "FOUNDATION_NOT_READY" for error in payload["errors"])
    assert requests == []


def test_plan_defaults_to_production_and_uses_project_provider_config(tmp_path):
    project = make_project(tmp_path)
    seed_foundation(project)
    server, base_url, requests = start_chat_server([brief_json(1, "Entry")])
    configure_provider(project, base_url)

    try:
        result = run_cli(
            "plan",
            "--project-root", str(project),
            "--chapter", "1",
            "--title", "Entry",
            "--format", "json",
            env=env_with_key(),
        )
    finally:
        server.shutdown()

    assert result.returncode == 0, result.stdout + result.stderr
    saved = json.loads(chapter_brief_path(project, 1).read_text(encoding="utf-8"))
    assert saved["goal"] == "Chapter 1 goal."
    assert requests[0]["authorization"] == "Bearer sk-v1-test-secret"
    assert requests[0]["body"]["model"] == "writer-v1"
    assert json.loads(result.stdout)["data"]["production"] is True


def test_write_defaults_to_production_and_external_extract(tmp_path):
    project = make_project(tmp_path)
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "Entry", "--demo", "--format", "json")
    server, base_url, requests = start_chat_server([draft_text(1), extraction_json(1)])
    configure_provider(project, base_url)

    try:
        result = run_cli(
            "write",
            "--project-root", str(project),
            "--chapter", "1",
            "--format", "json",
            env=env_with_key(),
        )
    finally:
        server.shutdown()

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["production"] is True
    assert payload["data"]["extract_provider"] == "openai_compatible"
    assert "bronze token" in chapter_md_path(project, 1, "Entry").read_text(encoding="utf-8")
    assert len(requests) == 2
    assert requests[0]["body"]["model"] == "writer-v1"
    assert requests[1]["body"]["model"] == "writer-v1"


def test_write_without_provider_config_blocks_before_writing(tmp_path):
    project = make_project(tmp_path)
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "Entry", "--demo", "--format", "json")

    result = run_cli("write", "--project-root", str(project), "--chapter", "1", "--format", "json")

    assert result.returncode == 5
    payload = json.loads(result.stdout)
    assert any(error["code"] == "PRODUCTION_PROVIDER_REQUIRED" for error in payload["errors"])
    assert not chapter_md_path(project, 1, "Entry").exists()
    assert not commit_path(project, 1).exists()


def test_extract_defaults_to_production_and_invalid_json_blocks(tmp_path):
    project = make_project(tmp_path)
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "Entry", "--demo", "--format", "json")
    chapter_md_path(project, 1, "Entry").write_text("Xiao Heng holds the bronze token.", encoding="utf-8")
    server, base_url, _requests = start_chat_server(["not-json"])
    configure_provider(project, base_url)

    try:
        result = run_cli(
            "extract",
            "--project-root", str(project),
            "--chapter", "1",
            "--format", "json",
            env=env_with_key(),
        )
    finally:
        server.shutdown()

    assert result.returncode == 5
    payload = json.loads(result.stdout)
    assert any(error["code"] == "INVALID_PROVIDER_OUTPUT" for error in payload["errors"])


def test_demo_write_keeps_local_pipeline(tmp_path):
    project = make_project(tmp_path)
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "Entry", "--demo", "--format", "json")

    result = run_cli("write", "--project-root", str(project), "--chapter", "1", "--demo", "--format", "json")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["production"] is False
    assert chapter_md_path(project, 1, "Entry").exists()


def test_ten_chapter_dogfood_uses_provider_and_updates_read_models(tmp_path):
    project = make_project(tmp_path)
    seed_foundation(project)
    responses = []
    for chapter in range(1, 11):
        responses.append(brief_json(chapter, f"Entry {chapter}"))
        responses.append(draft_text(chapter))
        responses.append(extraction_json(chapter))
    server, base_url, requests = start_chat_server(responses)
    configure_provider(project, base_url)

    try:
        for chapter in range(1, 11):
            plan = run_cli(
                "plan",
                "--project-root", str(project),
                "--chapter", str(chapter),
                "--title", f"Entry {chapter}",
                "--format", "json",
                env=env_with_key(),
            )
            assert plan.returncode == 0, plan.stdout + plan.stderr
            write = run_cli(
                "write",
                "--project-root", str(project),
                "--chapter", str(chapter),
                "--format", "json",
                env=env_with_key(),
            )
            assert write.returncode == 0, write.stdout + write.stderr
    finally:
        server.shutdown()

    state = json.loads(state_path(project).read_text(encoding="utf-8"))
    dashboard = run_cli("dashboard", "--project-root", str(project), "--format", "json")
    dashboard_payload = json.loads(dashboard.stdout)

    assert state["current_chapter"] == 10
    assert len(state["chapters"]) == 10
    assert len(requests) == 30
    assert dashboard.returncode == 0
    assert dashboard_payload["data"]["project"]["current_chapter"] == 10
    assert list((project / ".codex-writer" / "agents" / "运行记录").glob("*.json"))
