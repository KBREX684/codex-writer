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
    requests = []

    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self.__class__.requests.append({
            "path": self.path,
            "authorization": self.headers.get("authorization", ""),
            "body": json.loads(body),
        })
        payload = {
            "choices": [
                {"message": {"content": self.__class__.response_content}}
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
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "Entry", "--format", "json")

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
    run_cli("plan", "--project-root", str(project), "--chapter", "1", "--title", "Entry", "--format", "json")
    set_route(project, "draft_agent")
    draft = (
        "# Chapter 0001 Entry\n\n"
        "Xiao Heng obtained the bronze token before dawn and stepped into Blackwater City.\n\n"
        "\"Open the gate,\" he said. The guards fell silent as the seal cracked."
    )
    server, base_url, requests = start_chat_server(draft)
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
    assert requests[0]["body"]["model"] == "writer-test"


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
