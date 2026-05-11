import json
from pathlib import Path
from datetime import datetime, timezone

from codex_writer.core.io import write_json_atomic, read_json


def create_story_contract(title: str, genre: str) -> dict:
    return {
        "meta": {"schema_version": "codex-writer/story-contract/v1"},
        "book": {
            "title": title,
            "genre": genre,
            "target_platform": "",
            "target_length": ""
        },
        "core": {
            "one_sentence_pitch": "",
            "core_tone": "",
            "main_conflict": "",
            "reader_promise": []
        },
        "hard_rules": [],
        "world_rules": [],
        "main_characters": [],
        "style_rules": [],
        "forbidden_patterns": []
    }


def create_volume_contract(volume: int, title: str = "") -> dict:
    return {
        "volume": volume,
        "title": title,
        "goal": "",
        "key_milestones": [],
        "characters_introduced": [],
        "ending_hook": ""
    }


def create_project_json(title: str, genre: str) -> dict:
    return {
        "meta": {"schema_version": "codex-writer/project/v1"},
        "title": title,
        "genre": genre,
        "created_at": datetime.now(timezone.utc).isoformat()
    }


def create_initial_state_json() -> dict:
    return {
        "meta": {"schema_version": "codex-writer/state/v1"},
        "total_word_count": 0,
        "current_chapter": 0,
        "current_volume": 1,
        "chapters": {},
        "story_status": "planning"
    }


def create_initial_memory_json() -> dict:
    return {
        "meta": {"schema_version": "codex-writer/memory/v1"},
        "open_loops": [],
        "reader_promises": [],
        "world_rules": [],
        "long_term_facts": []
    }


def create_initial_anti_ai_feedback() -> list:
    return []


def create_agent_router_json() -> dict:
    return {
        "schema_version": "codex-writer/router/v1",
        "default_provider": "codex",
        "routes": {
            "planning_agent": {"provider": "codex", "model": "default"},
            "context_agent": {"provider": "codex", "model": "default"},
            "draft_agent": {"provider": "codex", "model": "default"},
            "review_agent": {"provider": "codex", "model": "default"},
            "polish_agent": {"provider": "codex", "model": "default"},
            "extract_agent": {"provider": "codex", "model": "default"},
            "query_agent": {"provider": "codex", "model": "default"}
        }
    }


def create_provider_example_json() -> dict:
    return {
        "_note": "本文件仅保存 provider 配置模板。API Key 请通过环境变量设置。",
        "providers": {
            "openai_compatible": {
                "base_url_env": "CODEX_WRITER_OPENAI_COMPATIBLE_BASE_URL",
                "api_key_env": "CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY",
                "model_env": "CODEX_WRITER_OPENAI_COMPATIBLE_MODEL"
            }
        }
    }
