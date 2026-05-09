import json

from codex_writer.agents.privacy import PrivacyPolicy, can_send_external
from codex_writer.agents.prompts import build_agent_prompt
from codex_writer.agents.router import load_default_router, route_agent
from codex_writer.agents.agents import write_agent_run
from codex_writer.observability.usage import estimate_usage


def test_default_router_uses_codex_for_review():
    router = load_default_router()
    route = route_agent(router, "review_agent")
    assert route["provider"] == "codex"


def test_privacy_blocks_full_manuscript_external_by_default():
    policy = PrivacyPolicy()
    allowed = can_send_external(policy, input_kind="full_manuscript", chars=10000)
    assert allowed is False


def test_write_agent_run_record(tmp_path):
    record = write_agent_run(
        tmp_path,
        {
            "task_id": "ch0001-draft_agent-run_x",
            "run_id": "run_x",
            "chapter": 1,
            "agent": "draft_agent",
            "provider": "codex",
            "model": "default",
            "status": "completed",
            "input_refs": [],
            "output_ref": "正文/第0001章-标题.md",
            "usage": {},
            "errors": [],
        },
    )
    assert record.exists()
    assert json.loads(record.read_text(encoding="utf-8"))["agent"] == "draft_agent"


def test_prompt_builder_has_agent_boundary_text():
    prompt = build_agent_prompt("draft_agent", {"chapter": 1})
    assert "draft_agent" in prompt["system_prompt"]
    assert "不能直接写入" in prompt["system_prompt"]
    assert "commits/" in prompt["system_prompt"]


def test_usage_estimate_records_chars_and_redaction_flag():
    usage = estimate_usage(provider="openai_compatible", model="writer-large", input_text="abc", output_text="正文")
    assert usage["input_chars"] == 3
    assert usage["output_chars"] == 2
    assert usage["redacted"] is True
