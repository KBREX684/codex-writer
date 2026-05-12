import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from codex_writer.core.paths import agent_router_path, chapter_brief_path, chapter_md_path


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


class ChatCompletionHandler(BaseHTTPRequestHandler):
    response_content = ""
    response_contents = []
    requests = []

    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self.__class__.requests.append({
            "path": self.path,
            "authorization": self.headers.get("authorization", ""),
            "body": json.loads(body),
        })
        content = self.__class__.response_contents.pop(0) if self.__class__.response_contents else self.__class__.response_content
        payload = {
            "choices": [
                {"message": {"content": content}}
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46},
        }
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        return


def start_chat_server(content):
    if isinstance(content, list):
        ChatCompletionHandler.response_contents = list(content)
        ChatCompletionHandler.response_content = content[-1] if content else ""
    else:
        ChatCompletionHandler.response_contents = []
        ChatCompletionHandler.response_content = content
    ChatCompletionHandler.requests = []
    server = HTTPServer(("127.0.0.1", 0), ChatCompletionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    return server, base_url, ChatCompletionHandler.requests


def make_project(tmp_path):
    project = tmp_path / "book"
    run_cli("init", "--project-root", str(project), "--title", "Book", "--genre", "xianxia", "--format", "json")
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


def set_route(project, agent, provider="openai_compatible", model="writer-test"):
    path = agent_router_path(project)
    router = json.loads(path.read_text(encoding="utf-8"))
    router.setdefault("routes", {})[agent] = {"provider": provider, "model": model}
    path.write_text(json.dumps(router, ensure_ascii=False, indent=2), encoding="utf-8")


def provider_env(base_url):
    return {
        "CODEX_WRITER_ALLOW_EXTERNAL_MODELS": "1",
        "CODEX_WRITER_OPENAI_COMPATIBLE_BASE_URL": base_url,
        "CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY": "sk-test",
        "CODEX_WRITER_OPENAI_COMPATIBLE_MODEL": "",
    }


def test_production_preflight_requires_external_planning_and_draft_routes(tmp_path):
    project = make_project(tmp_path)
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "Entry", "--demo", "--format", "json")

    result = run_cli(
        "preflight",
        "--project-root", str(project),
        "--chapter", "1",
        "--production",
        "--format", "json",
    )

    assert result.returncode == 5
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any(error["code"] == "PRODUCTION_PROVIDER_REQUIRED" for error in payload["errors"])


def test_plan_production_uses_openai_compatible_provider(tmp_path):
    project = make_project(tmp_path)
    seed_foundation(project)
    set_route(project, "planning_agent")
    brief = {
        "meta": {"schema_version": "codex-writer/chapter-brief/v1"},
        "chapter": 1,
        "title": "Entry",
        "goal": "Open with a concrete conflict.",
        "must_cover_nodes": [],
        "forbidden_zones": [],
        "key_entities": ["Xiao Heng"],
        "context_summary": "The bronze token appears.",
        "character_motivation": [],
        "style_guidance": [],
        "ending_hook": "A sealed gate opens.",
        "anti_ai_reminders": [],
    }
    server, base_url, requests = start_chat_server(json.dumps(brief))
    try:
        result = run_cli(
            "plan",
            "--project-root", str(project),
            "--chapter", "1",
            "--title", "Entry",
            "--production",
            "--format", "json",
            env=provider_env(base_url),
        )
    finally:
        server.shutdown()

    assert result.returncode == 0
    saved = json.loads(chapter_brief_path(project, 1).read_text(encoding="utf-8"))
    assert saved["goal"] == "Open with a concrete conflict."
    assert saved["key_entities"] == ["Xiao Heng"]
    assert requests[0]["path"] == "/v1/chat/completions"
    assert requests[0]["authorization"] == "Bearer sk-test"
    assert requests[0]["body"]["model"] == "writer-test"


def test_write_production_uses_external_draft_text(tmp_path):
    project = make_project(tmp_path)
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "Entry", "--demo", "--format", "json")
    set_route(project, "draft_agent")
    set_route(project, "extract_agent")
    draft = (
        "# Chapter 0001 Entry\n\n"
        "Xiao Heng obtained the bronze token before dawn and stepped into Blackwater City.\n\n"
        "\"Open the gate,\" he said. The guards fell silent as the seal cracked."
    )
    extraction = {
        "meta": {"schema_version": "codex-writer/extraction-result/v1"},
        "chapter": 1,
        "covered_nodes": [],
        "missed_nodes": [],
        "pending_disambiguation": [],
        "state_deltas": [],
        "entity_deltas": [],
        "entities_appeared": [{"entity": "Xiao Heng", "count": 1, "first_position": 2}],
        "accepted_events": [{
            "event_id": "ch0001-token",
            "chapter": 1,
            "event_type": "plot_node_covered",
            "subject": "bronze token",
            "payload": {"source": "test"},
        }],
        "scenes": [{"index": 1, "text_preview": "Xiao Heng obtained the bronze token"}],
        "summary_text": "Xiao Heng obtained the bronze token.",
        "dominant_thread": "bronze token",
    }
    server, base_url, requests = start_chat_server([draft, json.dumps(extraction)])
    try:
        result = run_cli(
            "write",
            "--project-root", str(project),
            "--chapter", "1",
            "--production",
            "--format", "json",
            env=provider_env(base_url),
        )
    finally:
        server.shutdown()

    assert result.returncode == 0
    chapter_text = chapter_md_path(project, 1, "Entry").read_text(encoding="utf-8")
    assert "bronze token" in chapter_text
    payload = json.loads(result.stdout)
    assert payload["data"]["production"] is True
    assert payload["data"]["extract_provider"] == "openai_compatible"
    assert requests[0]["body"]["model"] == "writer-test"
    assert requests[1]["body"]["model"] == "writer-test"


def test_run_agent_calls_openai_compatible_provider_when_routed(tmp_path):
    project = make_project(tmp_path)
    set_route(project, "draft_agent")
    server, base_url, requests = start_chat_server("agent output")
    try:
        result = run_cli(
            "run-agent",
            "--project-root", str(project),
            "--agent", "draft_agent",
            "--format", "json",
            env=provider_env(base_url),
        )
    finally:
        server.shutdown()

    assert result.returncode == 0
    assert requests[0]["body"]["model"] == "writer-test"
