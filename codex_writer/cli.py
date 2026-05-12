import argparse
import json
import os
import sys

from datetime import datetime, timezone
from pathlib import Path

from codex_writer.core.errors import CodexWriterError
from codex_writer.core.io import write_json_atomic, read_json
from codex_writer.story.contracts import (
    create_story_contract,
    create_volume_contract,
    create_project_json,
    create_initial_state_json,
    create_initial_memory_json,
    create_initial_anti_ai_feedback,
    create_agent_router_json,
    create_provider_config_json,
    create_provider_example_json,
)
from codex_writer.story.placeholders import scan_chapter_placeholders, scan_user_files_placeholders


def output_json(command: str, ok: bool = True, data: dict | None = None,
                warnings: list | None = None, errors: list | None = None,
                run_id: str = "", project_root: str = "") -> None:
    from codex_writer.core.security import redact_secret
    sensitive_keys = ("api_key", "apikey", "secret", "token", "password", "credential")

    def _redact(obj, key: str = ""):
        key_l = key.lower()
        if any(k in key_l for k in sensitive_keys):
            if key_l.endswith("_env"):
                return obj
            if isinstance(obj, (bool, int, float)) or obj is None:
                return obj
            if isinstance(obj, str):
                return redact_secret(obj)
            if obj:
                return "***"
            return obj
        if isinstance(obj, dict):
            return {k: _redact(v, k) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_redact(i) for i in obj]
        if isinstance(obj, str) and len(obj) > 20:
            if any(kw in str(obj).lower() for kw in ("api_key", "secret", "token", "password", "credential")):
                return redact_secret(obj)
        return obj
    payload = {
        "ok": ok,
        "command": command,
        "project_root": project_root,
        "run_id": run_id,
        "data": _redact(data or {}),
        "warnings": _redact(warnings or []),
        "errors": _redact(errors or []),
    }
    print(json.dumps(payload, ensure_ascii=False))


def _to_error_obj(e: CodexWriterError) -> dict:
    return {
        "code": e.code,
        "message": e.message or str(e),
        "blocking": e.exit_code in (2, 3, 4)
    }


def _normalize_chapter_brief(candidate: dict, chapter: int, title: str, fallback: dict | None = None) -> dict:
    brief = dict(fallback or {})
    if isinstance(candidate, dict):
        brief.update(candidate)
    brief["meta"] = {"schema_version": "codex-writer/chapter-brief/v1"}
    brief["chapter"] = chapter
    if not isinstance(brief.get("title"), str) or not brief["title"].strip():
        brief["title"] = title
    for key in ("goal", "context_summary", "ending_hook"):
        if not isinstance(brief.get(key), str):
            brief[key] = ""
    for key in (
        "must_cover_nodes",
        "forbidden_zones",
        "key_entities",
        "character_motivation",
        "style_guidance",
        "anti_ai_reminders",
    ):
        if not isinstance(brief.get(key), list):
            brief[key] = []
    return brief


def _provider_failure_errors(result: dict, empty_message: str) -> list[dict]:
    if result.get("error"):
        return [{"code": "PROVIDER_FAILURE", "message": str(result["error"]), "blocking": True}]
    if not result.get("text", "").strip() and not result.get("json"):
        return [{"code": "PROVIDER_EMPTY_OUTPUT", "message": empty_message, "blocking": True}]
    return []


def _is_demo(args) -> bool:
    return bool(getattr(args, "demo", False))


def _is_production(args) -> bool:
    return not _is_demo(args)


def _validate_external_extraction(candidate: dict, chapter: int) -> list[dict]:
    from codex_writer.extraction.schemas import validate_extraction_result

    if not isinstance(candidate, dict) or not candidate:
        return [{
            "code": "INVALID_PROVIDER_OUTPUT",
            "message": "extract_agent must return a non-empty JSON extraction result",
            "blocking": True,
        }]
    errors = validate_extraction_result(candidate)
    if candidate.get("chapter") != chapter:
        errors.append(f"chapter must match requested chapter: {chapter}")
    return [{"code": "INVALID_PROVIDER_OUTPUT", "message": e, "blocking": True} for e in errors]


def _external_extract_chapter(project_root: Path, chapter: int, title: str, brief: dict,
                              chapter_text: str) -> dict:
    from codex_writer.agents.execution import payload_chars, resolve_agent_provider

    payload = {
        "chapter": chapter,
        "title": title,
        "brief": brief,
        "chapter_text": chapter_text,
        "required_schema": "codex-writer/extraction-result/v1",
        "instruction": (
            "Return only a JSON object that matches codex-writer/extraction-result/v1. "
            "Do not include markdown fences unless they wrap valid JSON."
        ),
    }
    resolution = resolve_agent_provider(
        project_root,
        "extract_agent",
        require_external=True,
        input_kind="context_pack",
        input_chars=payload_chars(payload),
    )
    if resolution["errors"]:
        return {"ok": False, "exit_code": resolution["exit_code"], "errors": resolution["errors"]}

    input_text = json.dumps(payload, ensure_ascii=False)
    result = resolution["provider_obj"].generate({
        "system_prompt": "extract_agent: extract story state, events, scenes, and summary as strict JSON.",
        "task_prompt": input_text,
        "temperature": 0.2,
    })
    errors = _provider_failure_errors(result, "extract_agent returned no JSON")
    if not errors and not result.get("json"):
        errors = [{
            "code": "INVALID_PROVIDER_OUTPUT",
            "message": "extract_agent must return a JSON extraction result",
            "blocking": True,
        }]
    if not errors:
        errors = _validate_external_extraction(result["json"], chapter)
    if errors:
        return {"ok": False, "exit_code": 5, "errors": errors, "raw_result": result}

    return {
        "ok": True,
        "exit_code": 0,
        "result": result["json"],
        "provider": resolution["provider"],
        "model": resolution["model"],
        "usage": result.get("usage", {}),
        "input_text": input_text,
        "output_text": result.get("text", ""),
    }


def cmd_init(args):
    project_root = Path(args.project_root).resolve()
    cw = project_root / ".codex-writer"
    try:
        cw.mkdir(parents=True, exist_ok=True)
        for d in ["正文", "大纲", "设定", "审查报告"]:
            (project_root / d).mkdir(exist_ok=True)
        for d in [
            "story/volumes", "story/chapters", "story/reviews", "story/bible",
            "agents/运行记录", "events", "reviews", "commits",
            "summaries", "backups", "migrations", "logs", "tmp"
        ]:
            (cw / d).mkdir(parents=True, exist_ok=True)

        write_json_atomic(cw / "project.json", create_project_json(args.title, args.genre))
        write_json_atomic(cw / "state.json", create_initial_state_json())
        write_json_atomic(cw / "memory.json", create_initial_memory_json())
        from codex_writer.story.bible import create_novel_bible_template, write_novel_bible

        write_novel_bible(project_root, create_novel_bible_template(args.title, args.genre))
        write_json_atomic(cw / "story" / "故事合同.json", create_story_contract(args.title, args.genre))
        write_json_atomic(cw / "story" / "反AI反馈.json", [])
        write_json_atomic(cw / "story" / "volumes" / "第001卷合同.json", create_volume_contract(1))
        write_json_atomic(cw / "agents" / "子Agent路由.json", create_agent_router_json())
        write_json_atomic(cw / "agents" / "模型供应商.json", create_provider_config_json())
        write_json_atomic(cw / "agents" / "模型供应商.example.json", create_provider_example_json())
        write_json_atomic(cw / "migrations" / "applied.json", [])
        try:
            from codex_writer.genres.templates import match_genre_template

            template = match_genre_template(args.genre)
            if template:
                write_json_atomic(cw / "story" / "题材模板.json", template)
        except ImportError:
            pass

        output_json("init", data={"project_root": str(project_root), "title": args.title})
        return 0
    except Exception as e:
        output_json("init", ok=False, errors=[_to_error_obj(CodexWriterError(str(e)))])
        return 1


def cmd_doctor(args):
    from pathlib import Path
    from codex_writer.runtime.health import check_mainline_health
    from codex_writer.story.placeholders import scan_chapter_placeholders, scan_user_files_placeholders

    if args.self_check:
        from codex_writer import __version__

        repo_root = Path(__file__).resolve().parents[1]
        errors = []
        pyproject = repo_root / "pyproject.toml"
        plugin = repo_root / ".codex-plugin" / "plugin.json"
        expected_version = "1.0.0"
        if __version__ != expected_version:
            errors.append({"code": "VERSION_MISMATCH", "message": f"package version is {__version__}", "blocking": True})
        if pyproject.exists() and f'version = "{expected_version}"' not in pyproject.read_text(encoding="utf-8"):
            errors.append({"code": "VERSION_MISMATCH", "message": "pyproject version mismatch", "blocking": True})
        if plugin.exists():
            try:
                plugin_data = json.loads(plugin.read_text(encoding="utf-8"))
                if plugin_data.get("version") != expected_version:
                    errors.append({"code": "VERSION_MISMATCH", "message": "plugin manifest version mismatch", "blocking": True})
            except Exception:
                errors.append({"code": "PLUGIN_MANIFEST_INVALID", "message": "plugin manifest is not valid JSON", "blocking": True})
        release_files = [
            repo_root / "README.md",
            repo_root / "pyproject.toml",
            repo_root / "docs" / "guides" / "commands.md",
            repo_root / "docs" / "guides" / "public-beta.md",
            repo_root / "docs" / "releases" / "v1.0.md",
        ]
        release_files.extend((repo_root / "skills").glob("*/SKILL.md"))
        for path in release_files:
            if path.exists() and "MVP" in path.read_text(encoding="utf-8"):
                errors.append({"code": "MVP_COPY_RESIDUE", "message": f"MVP copy residue in {path.name}", "blocking": True})
        output_json("doctor", ok=not errors, data={"self_check": True, "version": __version__}, errors=errors)
        return 0 if not errors else 3

    project_root = Path(args.project_root).resolve()
    chapter = int(args.chapter) if args.chapter is not None else None
    health = check_mainline_health(project_root, chapter)
    errors = []
    warnings = []

    if args.strict:
        for w in health.get("warnings", []):
            errors.append({**w, "blocking": True})
    else:
        warnings = health.get("warnings", [])

    migrations = project_root / ".codex-writer" / "migrations" / "applied.json"
    if args.strict:
        if not migrations.exists():
            errors.append({"code": "MIGRATION_MISSING", "message": "迁移记录缺失", "blocking": True})
        else:
            try:
                applied = json.loads(migrations.read_text(encoding="utf-8"))
                if not applied:
                    errors.append({"code": "MIGRATION_MISSING", "message": "迁移记录为空，请运行 migrate", "blocking": True})
            except Exception:
                errors.append({"code": "MIGRATION_MISSING", "message": "迁移记录读取失败", "blocking": True})

    if args.strict:
        findings = scan_user_files_placeholders(project_root)
        if chapter is not None:
            findings.extend(scan_chapter_placeholders(project_root, chapter))
        for f in findings:
            errors.append({
                "code": "PLACEHOLDER_FOUND",
                "message": f"发现占位符: {f['text']} (第{f['line']}行, {f.get('file', 'unknown')})",
                "blocking": True
            })

    if args.strict:
        from codex_writer.agents.provider_config import PRODUCTION_AGENT_NAMES
        from codex_writer.agents.providers import OPENAI_COMPATIBLE
        from codex_writer.agents.router import load_project_router
        from codex_writer.core.paths import provider_config_path

        if not provider_config_path(project_root).exists():
            errors.append({
                "code": "PROVIDER_CONFIG_MISSING",
                "message": "生产模型供应商配置文件缺失，请运行 provider configure 或 migrate",
                "blocking": True,
            })
        router = load_project_router(project_root)
        routes = router.get("routes", {})
        missing_routes = [
            agent for agent in PRODUCTION_AGENT_NAMES
            if routes.get(agent, {}).get("provider") != OPENAI_COMPATIBLE
        ]
        if missing_routes:
            errors.append({
                "code": "PRODUCTION_ROUTE_INCOMPLETE",
                "message": "生产链路必须将 planning_agent、draft_agent、extract_agent 路由到外部 provider",
                "blocking": True,
                "agents": missing_routes,
            })

    if errors:
        exit_code = 3 if any(e.get("blocking", False) for e in errors) else 0
        output_json("doctor", ok=(exit_code == 0), project_root=str(project_root),
                    data=health, errors=errors, warnings=warnings)
        return exit_code

    output_json("doctor", project_root=str(project_root), data=health, warnings=warnings)
    return 0


def _first_volume_contract(project_root: Path) -> dict:
    from codex_writer.core.paths import resolve_in_project

    volumes_dir = resolve_in_project(project_root, ".codex-writer/story/volumes")
    if not volumes_dir.exists():
        return {}
    for path in sorted(volumes_dir.glob("*.json")):
        try:
            data = read_json(path)
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def _bible_project_defaults(project_root: Path) -> dict:
    from codex_writer.core.paths import project_json_path

    defaults = {"title": "", "genre": ""}
    path = project_json_path(project_root)
    if not path.exists():
        return defaults
    try:
        data = read_json(path)
    except (OSError, ValueError, TypeError):
        return defaults
    if isinstance(data, dict):
        defaults["title"] = str(data.get("title", "") or "")
        defaults["genre"] = str(data.get("genre", "") or "")
    return defaults


def _external_create_bible(args, project_root: Path, title: str, genre: str) -> dict:
    from codex_writer.agents.execution import payload_chars, resolve_agent_provider
    from codex_writer.core.paths import story_contract_path
    from codex_writer.story.bible import (
        create_novel_bible_template,
        normalize_novel_bible,
    )

    story_contract = {}
    story_path = story_contract_path(project_root)
    if story_path.exists():
        try:
            story_contract = read_json(story_path)
        except (OSError, ValueError, TypeError):
            story_contract = {}

    template = create_novel_bible_template(
        title,
        genre,
        target_words=int(args.target_words),
        target_chapters=int(args.target_chapters),
        volume_count=int(args.volume_count),
    )
    payload = {
        "task": "create_complete_million_word_novel_bible_before_chapter_one",
        "required_schema": "codex-writer/novel-bible/v1",
        "book": {"title": title, "genre": genre},
        "target_scale": {
            "target_words": int(args.target_words),
            "target_chapters": int(args.target_chapters),
            "volume_count": int(args.volume_count),
        },
        "author_input": args.author_input or "",
        "current_story_contract": story_contract,
        "first_volume_contract": _first_volume_contract(project_root),
        "schema_template": template,
        "instructions": [
            "Return only one JSON object. No markdown.",
            "The bible must be specific enough to support at least one million Chinese webnovel words.",
            "Fill every required section with concrete long-form planning, not slogans.",
            "Plan by book-level promise, world and power rules, character arcs, volume roadmap, plot debts, hooks, style contract, and runtime review contract.",
            "Do not set approval.status to approved. Approval is a separate author-controlled command.",
        ],
    }
    resolution = resolve_agent_provider(
        project_root,
        "planning_agent",
        require_external=True,
        input_kind="context_pack",
        input_chars=payload_chars(payload),
    )
    if resolution["errors"]:
        return {"ok": False, "exit_code": resolution["exit_code"], "errors": resolution["errors"]}

    input_text = json.dumps(payload, ensure_ascii=False)
    result = resolution["provider_obj"].generate({
        "system_prompt": (
            "planning_agent: create a complete codex-writer/novel-bible/v1 "
            "for a million-word Chinese webnovel. Return strict JSON only."
        ),
        "task_prompt": input_text,
        "temperature": 0.35,
    })
    errors = _provider_failure_errors(result, "planning_agent returned no novel bible JSON")
    if not errors and not result.get("json"):
        errors = [{
            "code": "INVALID_PROVIDER_OUTPUT",
            "message": "planning_agent must return a JSON novel bible",
            "blocking": True,
        }]
    if errors:
        return {"ok": False, "exit_code": 5, "errors": errors, "raw_result": result}

    bible = normalize_novel_bible(
        result["json"],
        title,
        genre,
        target_words=int(args.target_words),
        target_chapters=int(args.target_chapters),
        volume_count=int(args.volume_count),
    )
    return {
        "ok": True,
        "bible": bible,
        "provider": resolution["provider"],
        "model": resolution["model"],
        "usage": result.get("usage", {}),
        "input_text": input_text,
        "output_text": result.get("text", ""),
    }


def cmd_bible(args):
    from codex_writer.agents.agents import write_agent_run
    from codex_writer.core.paths import novel_bible_path
    from codex_writer.story.bible import (
        approve_novel_bible,
        create_demo_bible,
        load_novel_bible,
        validate_novel_bible,
        write_novel_bible,
    )

    project_root = Path(args.project_root).resolve()
    sub = args.bible_command
    if sub in ("status", "review"):
        bible = load_novel_bible(project_root)
        report = validate_novel_bible(bible)
        output_json("bible", ok=bible is not None, project_root=str(project_root), data={
            "path": str(novel_bible_path(project_root)),
            "bible": report,
            "approval_status": (bible or {}).get("approval", {}).get("status", ""),
        })
        return 0 if bible is not None else 3

    if sub == "approve":
        try:
            report = approve_novel_bible(
                project_root,
                approved_by=args.approved_by or "author",
                notes=args.notes or "",
            )
        except ValueError as exc:
            output_json("bible", ok=False, project_root=str(project_root), errors=[{
                "code": "BIBLE_INCOMPLETE",
                "message": str(exc),
                "blocking": True,
            }])
            return 3
        output_json("bible", project_root=str(project_root), data={
            "path": str(novel_bible_path(project_root)),
            "bible": report,
            "approval_status": "approved",
        })
        return 0

    if sub == "create":
        defaults = _bible_project_defaults(project_root)
        title = args.title or defaults["title"]
        genre = args.genre or defaults["genre"]
        existing_report = validate_novel_bible(load_novel_bible(project_root))
        if existing_report["ready"] and not args.force:
            output_json("bible", ok=False, project_root=str(project_root), data={"bible": existing_report}, errors=[{
                "code": "BIBLE_ALREADY_APPROVED",
                "message": "Approved novel bible already exists. Use --force to replace it.",
                "blocking": True,
            }])
            return 3

        if _is_demo(args):
            bible = create_demo_bible(
                title,
                genre,
                target_words=int(args.target_words),
                target_chapters=int(args.target_chapters),
                volume_count=int(args.volume_count),
            )
            provider_meta = {}
        else:
            external = _external_create_bible(args, project_root, title, genre)
            if not external["ok"]:
                output_json("bible", ok=False, project_root=str(project_root), errors=external["errors"])
                return external["exit_code"]
            bible = external["bible"]
            provider_meta = {
                "agent": "planning_agent",
                "provider": external["provider"],
                "model": external["model"],
            }
            run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            write_agent_run(project_root, {
                "task_id": f"novel-bible-planning_agent-{run_id}",
                "run_id": run_id,
                "chapter": 0,
                "agent": "planning_agent",
                "provider": external["provider"],
                "model": external["model"],
                "status": "completed",
                "input_refs": [],
                "usage": external.get("usage", {}),
                "errors": [],
            }, input_text=external.get("input_text", ""), output_text=external.get("output_text", ""))

        report = write_novel_bible(project_root, bible)
        errors = []
        if not report["content_ready"]:
            errors.append({
                "code": "BIBLE_INCOMPLETE",
                "message": "Novel bible content is incomplete and cannot be approved yet.",
                "blocking": True,
                "missing": report["missing"],
            })
        output_json(
            "bible",
            ok=not errors,
            project_root=str(project_root),
            data={
                "path": str(novel_bible_path(project_root)),
                "bible": report,
                "approval_status": bible.get("approval", {}).get("status", ""),
                "production_provider": provider_meta,
            },
            errors=errors,
        )
        return 0 if not errors else 5

    output_json("bible", ok=False, project_root=str(project_root), errors=[{
        "code": "INVALID_SUBCOMMAND",
        "message": "Use: bible create|review|status|approve",
        "blocking": True,
    }])
    return 2


def cmd_plan(args):
    project_root = Path(args.project_root).resolve()
    try:
        chapter = int(args.chapter)
    except (ValueError, TypeError):
        output_json("plan", ok=False, errors=[{"code": "INVALID_ARGUMENT", "message": f"chapter 必须为整数，收到: {args.chapter}", "blocking": True}])
        return 2
    from codex_writer.core.io import write_json_atomic
    brief_title = args.title or f"第{chapter:04d}章"
    brief = {
        "meta": {"schema_version": "codex-writer/chapter-brief/v1"},
        "chapter": chapter,
        "title": brief_title,
        "goal": "",
        "must_cover_nodes": [],
        "forbidden_zones": [],
        "key_entities": [],
        "context_summary": "",
        "character_motivation": [],
        "style_guidance": [],
        "ending_hook": "",
        "anti_ai_reminders": []
    }

    suggestions = {}
    try:
        from codex_writer.core.paths import project_json_path
        from codex_writer.genres.templates import apply_template_to_brief, match_genre_template

        pj = project_json_path(project_root)
        if pj.exists():
            project_data = read_json(pj)
            template = match_genre_template(project_data.get("genre", ""))
            if template:
                brief = apply_template_to_brief(brief, template)
                suggestions["genre_template"] = template["name"]
    except (ImportError, OSError, ValueError, KeyError):
        pass

    try:
        from codex_writer.references.search import search_references
        hits = search_references(project_root, brief_title, top_k=5)
        if hits:
            style_hints = [h["snippet"][:100] for h in hits if "节奏" in h.get("snippet", "") or "爽点" in h.get("snippet", "")]
            if style_hints:
                brief["style_guidance"] = style_hints[:3]
                suggestions["style_guidance"] = f"从 references 匹配到 {len(style_hints)} 条写作建议"
            tech_hints = [h["snippet"][:80] for h in hits if "技法" in h.get("path", "") or "叙事" in h.get("snippet", "")]
            if tech_hints:
                brief["context_summary"] = f"建议关注：{'；'.join(tech_hints[:2])}"
                suggestions["context_summary"] = f"从 references 匹配到 {len(tech_hints)} 条技法参考"
    except ImportError:
        pass

    production = _is_production(args)
    if production and chapter == 1:
        from codex_writer.story.foundation import check_foundation_ready, foundation_not_ready_error

        foundation = check_foundation_ready(project_root)
        if not foundation["ready"]:
            output_json(
                "plan",
                ok=False,
                project_root=str(project_root),
                data={
                    "chapter": chapter,
                    "title": brief_title,
                    "production": production,
                    "foundation": foundation,
                },
                errors=[foundation_not_ready_error(foundation)],
            )
            return 3

    if production:
        from codex_writer.agents.execution import payload_chars, resolve_agent_provider
        from codex_writer.agents.agents import write_agent_run
        from codex_writer.core.paths import story_contract_path
        from codex_writer.story.bible import load_novel_bible

        story_contract = {}
        story_path = story_contract_path(project_root)
        if story_path.exists():
            try:
                story_contract = read_json(story_path)
            except (OSError, ValueError, TypeError):
                story_contract = {}

        payload = {
            "chapter": chapter,
            "title": brief_title,
            "seed_brief": brief,
            "novel_bible": load_novel_bible(project_root) or {},
            "story_contract": story_contract,
            "first_volume_contract": _first_volume_contract(project_root),
            "required_schema": "codex-writer/chapter-brief/v1",
            "instruction": "Return only a JSON object for a chapter brief. Use the approved novel bible as the highest creative contract.",
        }
        resolution = resolve_agent_provider(
            project_root,
            "planning_agent",
            require_external=True,
            input_kind="context_pack",
            input_chars=payload_chars(payload),
        )
        if resolution["errors"]:
            output_json("plan", ok=False, project_root=str(project_root), errors=resolution["errors"])
            return resolution["exit_code"]

        result = resolution["provider_obj"].generate({
            "system_prompt": "planning_agent: create a production chapter brief as strict JSON.",
            "task_prompt": json.dumps(payload, ensure_ascii=False),
            "temperature": 0.4,
        })
        errors = _provider_failure_errors(result, "planning_agent returned no JSON")
        if not errors and not result.get("json"):
            errors = [{
                "code": "INVALID_PROVIDER_OUTPUT",
                "message": "planning_agent must return a JSON chapter brief",
                "blocking": True,
            }]
        if errors:
            output_json("plan", ok=False, project_root=str(project_root), errors=errors)
            return 5

        brief = _normalize_chapter_brief(result["json"], chapter, brief_title, fallback=brief)
        suggestions["production_provider"] = {
            "agent": "planning_agent",
            "provider": resolution["provider"],
            "model": resolution["model"],
        }
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        write_agent_run(project_root, {
            "task_id": f"ch{chapter:04d}-planning_agent-{run_id}",
            "run_id": run_id,
            "chapter": chapter,
            "agent": "planning_agent",
            "provider": resolution["provider"],
            "model": resolution["model"],
            "status": "completed",
            "input_refs": [],
            "usage": result.get("usage", {}),
            "errors": [],
        }, input_text=json.dumps(payload, ensure_ascii=False), output_text=result.get("text", ""))

    if args.dry_run:
        output_json("plan", data={"chapter": chapter, "title": brief_title, "suggestions": suggestions, "dry_run": True, "production": production}, project_root=str(project_root))
        return 0

    path = project_root / ".codex-writer" / "story" / "chapters" / f"第{chapter:04d}章任务书.json"
    write_json_atomic(path, brief)
    output_json("plan", data={"chapter": chapter, "title": brief_title, "suggestions": suggestions, "production": production}, project_root=str(project_root))
    return 0


def cmd_context(args):
    from pathlib import Path
    from codex_writer.story.context import write_context_pack
    from codex_writer.memory.scratchpad import query_memory, get_active_loops
    project_root = Path(args.project_root).resolve()
    chapter = int(args.chapter)
    path = write_context_pack(project_root, chapter)
    import json
    pack = json.loads(path.read_text(encoding="utf-8"))
    loops = get_active_loops(project_root)
    pack["open_loops"] = loops if loops else pack.get("open_loops", [])
    pack["memory_count"] = len(query_memory(project_root))
    output_json("context", data=pack, project_root=str(project_root))
    return 0


def cmd_write(args):
    from pathlib import Path
    from datetime import datetime, timezone
    from codex_writer.core.io import write_json_atomic, write_markdown_atomic, read_json
    from codex_writer.core.workflow import log_workflow
    from codex_writer.core.paths import chapter_brief_path, chapter_md_path, extraction_result_path
    from codex_writer.review.pipeline import run_review
    from codex_writer.review.anti_ai import append_anti_ai_feedback
    from codex_writer.extraction.extractor import extract_from_chapter
    from codex_writer.commit.service import commit_chapter, mark_projection_done
    from codex_writer.commit.events import write_chapter_events, mirror_events_to_db
    from codex_writer.projections.state import chapter_text_word_count
    from codex_writer.agents.agents import write_agent_run
    from codex_writer.story.context import write_context_pack

    project_root = Path(args.project_root).resolve()
    chapter = int(args.chapter)
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    warnings = []
    errors = []
    production = _is_production(args)

    log_workflow(project_root, run_id, chapter, "planned", "context_ready", "workflow", "")

    brief_path = chapter_brief_path(project_root, chapter)
    if not brief_path.exists():
        errors.append({"code": "CHAPTER_BRIEF_MISSING", "message": f"第{chapter}章任务书缺失", "blocking": True})
        log_workflow(project_root, run_id, chapter, "context_ready", "blocked", "workflow", "")
        output_json("write", ok=False, project_root=str(project_root), run_id=run_id, warnings=warnings, errors=errors)
        return 3

    story_contract = project_root / ".codex-writer" / "story" / "故事合同.json"
    if not story_contract.exists():
        errors.append({"code": "STORY_CONTRACT_MISSING", "message": "故事合同缺失", "blocking": True})
        log_workflow(project_root, run_id, chapter, "context_ready", "blocked", "workflow", "")
        output_json("write", ok=False, project_root=str(project_root), run_id=run_id, warnings=warnings, errors=errors)
        return 3

    if production and chapter == 1:
        from codex_writer.story.foundation import check_foundation_ready, foundation_not_ready_error

        foundation = check_foundation_ready(project_root)
        if not foundation["ready"]:
            output_json(
                "write",
                ok=False,
                project_root=str(project_root),
                run_id=run_id,
                data={"chapter": chapter, "production": production, "foundation": foundation},
                errors=[foundation_not_ready_error(foundation)],
            )
            return 3

    log_workflow(project_root, run_id, chapter, "context_ready", "drafted", "draft_agent", "")
    context_pack_path = None
    try:
        from codex_writer.story.context import write_context_pack
        context_pack_path = write_context_pack(project_root, chapter)
    except Exception:
        warnings.append({"code": "CONTEXT_PACK_FAILED", "message": "写前资料包生成失败，继续执行"})

    brief = read_json(brief_path)
    title = brief.get("title", f"第{chapter:04d}章")
    draft_provider = "codex"
    draft_model = "default"
    draft_usage = {}
    draft_input_text = ""
    if production:
        from codex_writer.agents.execution import payload_chars, resolve_agent_provider

        context_pack = {}
        context_path = context_pack_path
        if context_path and context_path.exists():
            try:
                context_pack = read_json(context_path)
            except Exception:
                context_pack = {}
        payload = {
            "chapter": chapter,
            "title": title,
            "brief": brief,
            "context_pack": context_pack,
            "instruction": "Return polished chapter prose as markdown text. Do not return JSON.",
        }
        resolution = resolve_agent_provider(
            project_root,
            "draft_agent",
            require_external=True,
            input_kind="context_pack",
            input_chars=payload_chars(payload),
        )
        if resolution["errors"]:
            errors.extend(resolution["errors"])
            log_workflow(project_root, run_id, chapter, "context_ready", "blocked", "draft_agent", "")
            output_json("write", ok=False, project_root=str(project_root), run_id=run_id, warnings=warnings, errors=errors)
            return resolution["exit_code"]
        draft_input_text = json.dumps(payload, ensure_ascii=False)
        result = resolution["provider_obj"].generate({
            "system_prompt": "draft_agent: write the chapter prose. Return only markdown prose.",
            "task_prompt": draft_input_text,
            "temperature": 0.75,
        })
        provider_errors = _provider_failure_errors(result, "draft_agent returned empty prose")
        if provider_errors:
            errors.extend(provider_errors)
            log_workflow(project_root, run_id, chapter, "context_ready", "blocked", "draft_agent", "")
            output_json("write", ok=False, project_root=str(project_root), run_id=run_id, warnings=warnings, errors=errors)
            return 5
        draft_text = result.get("text", "").strip()
        draft_provider = resolution["provider"]
        draft_model = resolution["model"]
        draft_usage = result.get("usage", {})
    else:
        draft_text = f"第{chapter:04d}章 {title}\n\n萧衡站在旧城门前，握紧刚得到的青铜令。\n他知道，自己必须前往黑水城，查清令牌背后的来历。\n"
    md_path = chapter_md_path(project_root, chapter, title)
    write_markdown_atomic(md_path, draft_text)
    write_agent_run(project_root, {
        "task_id": f"ch{chapter:04d}-draft_agent-run_{run_id}",
        "run_id": run_id, "chapter": chapter,
        "agent": "draft_agent", "provider": draft_provider, "model": draft_model,
        "status": "completed", "input_refs": [], "usage": draft_usage, "errors": []
    }, input_text=draft_input_text, output_text=draft_text)

    log_workflow(project_root, run_id, chapter, "drafted", "reviewed", "review_agent", "")
    review_result = run_review(project_root, chapter)
    append_anti_ai_feedback(project_root, review_result.get("issues", []), current_chapter=chapter)
    write_agent_run(project_root, {
        "task_id": f"ch{chapter:04d}-review_agent-run_{run_id}",
        "run_id": run_id, "chapter": chapter,
        "agent": "review_agent", "provider": "codex", "model": "default",
        "status": "completed", "input_refs": [], "usage": {}, "errors": []
    })

    if review_result["blocking_count"] > 0:
        log_workflow(project_root, run_id, chapter, "reviewed", "rejected", "review_agent", "")
        errors.append({"code": "REVIEW_BLOCKING", "message": f"审查阻断: {review_result['blocking_count']} 个问题", "blocking": True})
        output_json("write", ok=False, project_root=str(project_root), run_id=run_id, warnings=warnings, errors=errors)
        return 3

    log_workflow(project_root, run_id, chapter, "reviewed", "polished", "polish_agent", "")
    write_agent_run(project_root, {
        "task_id": f"ch{chapter:04d}-polish_agent-run_{run_id}",
        "run_id": run_id, "chapter": chapter,
        "agent": "polish_agent", "provider": "codex", "model": "default",
        "status": "completed", "input_refs": [], "usage": {}, "errors": []
    })

    log_workflow(project_root, run_id, chapter, "polished", "extracted", "extract_agent", "")
    extract_provider = "codex"
    extract_model = "default"
    extract_usage = {}
    extract_input_text = ""
    extract_output_text = ""
    if production:
        extraction = _external_extract_chapter(project_root, chapter, title, brief, draft_text)
        if not extraction["ok"]:
            errors.extend(extraction["errors"])
            log_workflow(project_root, run_id, chapter, "polished", "blocked", "extract_agent", "")
            output_json("write", ok=False, project_root=str(project_root), run_id=run_id, warnings=warnings, errors=errors)
            return extraction["exit_code"]
        extract_result = extraction["result"]
        write_json_atomic(extraction_result_path(project_root, chapter), extract_result)
        extract_provider = extraction["provider"]
        extract_model = extraction["model"]
        extract_usage = extraction["usage"]
        extract_input_text = extraction["input_text"]
        extract_output_text = extraction["output_text"]
    else:
        extract_result = extract_from_chapter(project_root, chapter)
    write_agent_run(project_root, {
        "task_id": f"ch{chapter:04d}-extract_agent-run_{run_id}",
        "run_id": run_id, "chapter": chapter,
        "agent": "extract_agent", "provider": extract_provider, "model": extract_model,
        "status": "completed", "input_refs": [], "usage": extract_usage, "errors": []
    }, input_text=extract_input_text, output_text=extract_output_text)

    log_workflow(project_root, run_id, chapter, "extracted", "committed", "commit", "")
    commit = commit_chapter(project_root, chapter, no_backup=args.no_backup)

    events_data = commit.get("accepted_events", [])
    write_chapter_events(project_root, chapter, events_data)
    if events_data:
        mirror_events_to_db(project_root, chapter, events_data)

    _apply_projections(project_root, chapter, commit, events_data)

    if commit["meta"]["status"] == "accepted":
        from codex_writer.reading_power.tracker import detect_hooks_from_text, expire_old_debts, add_debt
        hooks_found = detect_hooks_from_text(draft_text, chapter)
        for hook in hooks_found:
            add_debt(project_root, chapter, hook.get("snippet", hook.get("type", "")), debt_type=hook.get("type", "hook"))
        expire_old_debts(project_root, chapter)
        commit = mark_projection_done(project_root, chapter, commit)
        log_workflow(project_root, run_id, chapter, "committed", "projected", "projections", "")
    else:
        log_workflow(project_root, run_id, chapter, "committed", "rejected", "commit", "")
        errors.append({"code": "COMMIT_REJECTED", "message": "章节被拒绝", "blocking": True})
        output_json("write", ok=False, data=commit, project_root=str(project_root), run_id=run_id, warnings=warnings, errors=errors)
        return 3

    output_json("write", data={
        "chapter": chapter,
        "title": title,
        "status": commit["meta"]["status"],
        "word_count": chapter_text_word_count(project_root, chapter, commit.get("summary_text", "")),
        "run_id": run_id,
        "production": production,
        "draft_provider": draft_provider,
        "draft_model": draft_model,
        "extract_provider": extract_provider,
        "extract_model": extract_model
    }, project_root=str(project_root), run_id=run_id, warnings=warnings)
    return 0


def cmd_review(args):
    from pathlib import Path
    from codex_writer.review.pipeline import run_review
    from codex_writer.review.anti_ai import append_anti_ai_feedback
    project_root = Path(args.project_root).resolve()
    chapter = int(args.chapter)
    result = run_review(project_root, chapter)
    append_anti_ai_feedback(project_root, result.get("issues", []), current_chapter=chapter)
    if result["blocking_count"] > 0:
        output_json("review", ok=False, data=result, project_root=str(project_root),
                    errors=[{"code": "REVIEW_BLOCKING", "message": f"审查发现 {result['blocking_count']} 个阻断问题", "blocking": True}])
        return 3
    output_json("review", data=result, project_root=str(project_root))
    return 0


def cmd_extract(args):
    from pathlib import Path
    from codex_writer.extraction.extractor import extract_from_chapter
    from codex_writer.extraction.schemas import validate_extraction_result
    from codex_writer.core.io import read_json, write_json_atomic
    from codex_writer.core.paths import chapter_brief_path, chapter_md_path, extraction_result_path
    project_root = Path(args.project_root).resolve()
    chapter = int(args.chapter)
    if _is_production(args):
        brief = {}
        brief_path = chapter_brief_path(project_root, chapter)
        if brief_path.exists():
            brief = read_json(brief_path)
        title = brief.get("title", "")
        md_path = chapter_md_path(project_root, chapter, title)
        chapter_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        extraction = _external_extract_chapter(project_root, chapter, title, brief, chapter_text)
        if not extraction["ok"]:
            output_json("extract", ok=False, project_root=str(project_root), errors=extraction["errors"])
            return extraction["exit_code"]
        result = extraction["result"]
        write_json_atomic(extraction_result_path(project_root, chapter), result)
    else:
        result = extract_from_chapter(project_root, chapter)
    errors = validate_extraction_result(result)
    if errors:
        output_json("extract", ok=False, project_root=str(project_root),
                    errors=[{"code": "SCHEMA_VALIDATION_FAILED", "message": e, "blocking": True} for e in errors])
        return 2
    output_json("extract", data={
        "chapter": chapter,
        "summary_text": result["summary_text"],
        "production": _is_production(args),
    }, project_root=str(project_root))
    return 0


def cmd_commit_cli(args):
    from pathlib import Path
    from codex_writer.commit.service import commit_chapter, mark_projection_done
    from codex_writer.commit.events import write_chapter_events, mirror_events_to_db
    from codex_writer.core.errors import CodexWriterError

    project_root = Path(args.project_root).resolve()
    chapter = int(args.chapter)

    try:
        commit = commit_chapter(project_root, chapter, no_backup=args.no_backup)
    except CodexWriterError as e:
        output_json("commit", ok=False, project_root=str(project_root),
                    errors=[{"code": e.code, "message": e.message, "blocking": True}])
        return e.exit_code

    events = commit.get("accepted_events", [])
    write_chapter_events(project_root, chapter, events)
    if events:
        mirror_events_to_db(project_root, chapter, events)

    _apply_projections(project_root, chapter, commit, events)

    if commit["meta"]["status"] == "accepted":
        commit = mark_projection_done(project_root, chapter, commit)

    if commit["meta"]["status"] == "rejected":
        output_json("commit", ok=False, data=commit, project_root=str(project_root),
                    errors=[{"code": "COMMIT_REJECTED", "message": "章节被拒绝", "blocking": True}])
        return 3

    output_json("commit", data=commit, project_root=str(project_root))
    return 0


def cmd_query(args):
    from pathlib import Path
    from codex_writer.query import query_entity, query_loops
    project_root = Path(args.project_root).resolve()
    if args.entity == "entity" and args.name:
        result = query_entity(project_root, args.name)
        output_json("query", data=result, project_root=str(project_root))
    elif args.entity == "loops":
        loops = query_loops(project_root)
        output_json("query", data={"loops": loops}, project_root=str(project_root))
    else:
        output_json("query", data={"help": "Use: query entity --name NAME  or  query loops"}, project_root=str(project_root))
    return 0


def cmd_status(args):
    from pathlib import Path
    from codex_writer.core.io import read_json
    from codex_writer.core.paths import state_path, memory_path, index_db_path
    from codex_writer.runtime.rag import get_search_mode
    project_root = Path(args.project_root).resolve()
    sp = state_path(project_root)
    data = {}
    if sp.exists():
        state = read_json(sp)
        data = {"state": state}
        if hasattr(args, 'focus') and args.focus == 'all':
            mem = memory_path(project_root)
            if mem.exists():
                data["memory"] = read_json(mem)
            data["rag_mode"] = get_search_mode(project_root)
        if hasattr(args, 'focus') and args.focus == 'memory':
            mem = memory_path(project_root)
            if mem.exists():
                data["memory"] = read_json(mem)
        if hasattr(args, 'focus') and args.focus == 'rag':
            data["rag_mode"] = get_search_mode(project_root)
        output_json("status", data=data, project_root=str(project_root))
    else:
        output_json("status", ok=False, project_root=str(project_root),
                    errors=[{"code": "STATE_MISSING", "message": "state.json 不存在", "blocking": False}])
    return 0


def cmd_events(args):
    from pathlib import Path
    import sqlite3
    from codex_writer.commit.events import read_chapter_events
    project_root = Path(args.project_root).resolve()

    if args.health:
        events_path_obj = project_root / ".codex-writer" / "events"
        event_files = list(events_path_obj.glob("*.json")) if events_path_obj.exists() else []
        total_file_events = 0
        for ef in event_files:
            try:
                data = json.loads(ef.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    total_file_events += len(data)
            except json.JSONDecodeError:
                pass
        db_path = project_root / ".codex-writer" / "index.sqlite"
        sqlite_count = 0
        if db_path.exists():
            with sqlite3.connect(str(db_path)) as conn:
                try:
                    row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
                    sqlite_count = row[0] if row else 0
                except sqlite3.OperationalError:
                    sqlite_count = 0
        consistent = total_file_events == sqlite_count
        output_json("events", data={
            "event_files": len(event_files),
            "sqlite_events": sqlite_count,
            "total_file_events": total_file_events,
            "consistent": consistent
        }, project_root=str(project_root))
        return 0

    if args.chapter:
        chapter = int(args.chapter)
        events_data = read_chapter_events(project_root, chapter)
        output_json("events", data={"events": events_data}, project_root=str(project_root))
        return 0

    output_json("events", data={"help": "Use: events --chapter N  or  events --health"}, project_root=str(project_root))
    return 0


def cmd_migrate(args):
    from pathlib import Path
    from codex_writer.agents.provider_config import ensure_provider_config
    from codex_writer.storage.migrations import migrate
    project_root = Path(args.project_root).resolve()
    migrate(project_root)
    ensure_provider_config(project_root)
    output_json("migrate", data={"migrated": True}, project_root=str(project_root))
    return 0


def cmd_backup(args):
    from pathlib import Path
    from codex_writer.storage.backup import create_backup_manifest, list_backups, verify_backup
    project_root = Path(args.project_root).resolve()
    if hasattr(args, 'sub_command') and args.sub_command == 'list':
        blist = list_backups(project_root)
        output_json("backup", data={"backups": blist}, project_root=str(project_root))
        return 0
    if hasattr(args, 'sub_command') and args.sub_command == 'verify':
        vresult = verify_backup(project_root, args.backup_id)
        output_json("backup", data=vresult, project_root=str(project_root))
        return 0
    manifest = create_backup_manifest(project_root, reason=args.reason)
    output_json("backup", data=manifest, project_root=str(project_root))
    return 0


def cmd_restore(args):
    from pathlib import Path
    import shutil
    project_root = Path(args.project_root).resolve()
    backup_dir = project_root / ".codex-writer" / "backups" / args.backup_id
    if not backup_dir.exists():
        output_json("restore", ok=False, project_root=str(project_root),
                    errors=[{"code": "BACKUP_NOT_FOUND", "message": f"备份 {args.backup_id} 不存在", "blocking": True}])
        return 3
    cw = project_root / ".codex-writer"
    for f in backup_dir.iterdir():
        if f.is_file() and f.name != "manifest.json":
            dst = cw / f.name
            if dst.exists() and not dst.is_dir():
                shutil.copy2(str(f), str(dst))
    output_json("restore", data={"restored": args.backup_id}, project_root=str(project_root))
    return 0


def cmd_repair(args):
    from pathlib import Path
    from codex_writer.core.io import read_json, write_json_atomic
    from codex_writer.projections.index import update_index_from_commit
    from codex_writer.core.paths import commit_path
    project_root = Path(args.project_root).resolve()

    if args.sub == "projections":
        if args.action_all:
            commits_dir = project_root / ".codex-writer" / "commits"
            if not commits_dir.exists():
                output_json("repair", ok=False, project_root=str(project_root),
                            errors=[{"code": "NO_COMMITS", "message": "commits 目录不存在"}])
                return 3
            repaired = 0
            for cp in sorted(commits_dir.glob("*.json")):
                ch_num = int(cp.stem.replace("第", "").replace("章提交", "").replace("提交", "").replace("第", ""))
                try:
                    ch_num = int(''.join(c for c in cp.stem if c.isdigit()))
                except (ValueError, IndexError):
                    continue
                if ch_num == 0:
                    continue
                try:
                    commit = read_json(cp)
                    _apply_projections(project_root, ch_num, commit, commit.get("accepted_events", []))
                    repaired += 1
                except (OSError, ValueError, KeyError):
                    pass
            output_json("repair", data={"repaired": f"{repaired} chapters"}, project_root=str(project_root))
            return 0
        elif args.chapter:
            chapter = int(args.chapter)
            cp = commit_path(project_root, chapter)
            if cp.exists():
                commit = read_json(cp)
                _apply_projections(project_root, chapter, commit, commit.get("accepted_events", []))
                output_json("repair", data={"repaired": f"projections chapter {chapter}"}, project_root=str(project_root))
            else:
                output_json("repair", ok=False, project_root=str(project_root),
                            errors=[{"code": "COMMIT_MISSING", "message": f"第{chapter}章提交缺失", "blocking": True}])
                return 3
        else:
            output_json("repair", ok=False, project_root=str(project_root),
                        errors=[{"code": "NEED_CHAPTER", "message": "Use: repair projections --chapter N or repair projections --all"}])
            return 2
    elif args.sub == "index":
        if args.action_from_commits:
            from codex_writer.storage.db import init_schema
            init_schema(project_root)
            commits_dir = project_root / ".codex-writer" / "commits"
            count = 0
            if commits_dir.exists():
                for cp in sorted(commits_dir.glob("*.json")):
                    try:
                        commit = read_json(cp)
                        chapter = commit["meta"]["chapter"]
                        update_index_from_commit(project_root, chapter, commit)
                        count += 1
                    except (OSError, ValueError, KeyError):
                        pass
            output_json("repair", data={"repaired": f"index from {count} commits"}, project_root=str(project_root))
        else:
            from codex_writer.storage.db import init_schema
            init_schema(project_root)
            output_json("repair", data={"repaired": "index"}, project_root=str(project_root))
        return 0
    elif args.sub == "logs":
        from codex_writer.storage.db import insert_agent_run
        run_dir = project_root / ".codex-writer" / "agents" / "运行记录"
        count = 0
        if run_dir.exists():
            for run_file in run_dir.glob("*.json"):
                try:
                    insert_agent_run(project_root, read_json(run_file))
                    count += 1
                except (OSError, ValueError, KeyError):
                    pass
        output_json("repair", data={"agent_runs_rebuilt": count}, project_root=str(project_root))
        return 0
    else:
        output_json("repair", ok=False, project_root=str(project_root),
                    errors=[{"code": "INVALID_SUB", "message": f"Unknown subcommand: {args.sub}", "blocking": True}])
        return 2


def cmd_agents(args):
    from pathlib import Path
    from codex_writer.agents.router import load_project_router
    from codex_writer.agents.privacy import load_privacy_from_env
    project_root = Path(args.project_root).resolve()
    router = load_project_router(project_root)
    privacy = load_privacy_from_env()
    output_json("agents", data={
        "router": router,
        "privacy": {
            "allow_external_models": privacy.allow_external_models,
            "allow_full_manuscript_upload": privacy.allow_full_manuscript_upload,
            "max_context_chapters_external": privacy.max_context_chapters_external
        }
    }, project_root=str(project_root))
    return 0


def cmd_provider(args):
    from pathlib import Path
    from codex_writer.agents.provider_config import (
        OPENAI_COMPATIBLE_API_KEY_ENV,
        provider_presets_public,
        public_runtime_status,
        resolve_openai_compatible_options,
        save_provider_config,
    )
    from codex_writer.agents.providers import OPENAI_COMPATIBLE, create_provider, provider_config_errors
    from codex_writer.core.config import load_settings

    project_root = Path(args.project_root).resolve()
    sub = getattr(args, "provider_subcommand", "") or ""
    if sub == "presets":
        output_json("provider", data={"presets": provider_presets_public()}, project_root=str(project_root))
        return 0
    if sub == "configure":
        try:
            config = save_provider_config(
                project_root,
                preset=args.preset,
                base_url=args.base_url or "",
                model=args.model or "",
                timeout=args.timeout,
                max_tokens=args.max_tokens,
            )
        except ValueError as exc:
            output_json("provider", ok=False, project_root=str(project_root),
                        errors=[{"code": "INVALID_PROVIDER_PRESET", "message": str(exc), "blocking": True}])
            return 2
        output_json("provider", data={
            "provider": config["provider"],
            "api_key_env": OPENAI_COMPATIBLE_API_KEY_ENV,
            "production_agents": ["planning_agent", "draft_agent", "extract_agent"],
        }, project_root=str(project_root))
        return 0
    if sub == "status":
        output_json("provider", data={"provider": public_runtime_status(project_root)}, project_root=str(project_root))
        return 0
    if sub == "test":
        settings = load_settings()
        options = resolve_openai_compatible_options(
            project_root,
            cli_overrides={
                "preset": args.preset or "",
                "base_url": args.base_url or "",
                "model": args.model or "",
                "timeout": args.timeout,
                "max_tokens": args.max_tokens,
            },
            settings=settings,
        )
        errors = provider_config_errors(
            OPENAI_COMPATIBLE,
            settings,
            options["model"],
            base_url=options["base_url"],
            api_key=options["api_key"],
        )
        if errors:
            output_json("provider", ok=False, project_root=str(project_root),
                        data={"provider": public_runtime_status(project_root)}, errors=errors)
            return 5
        provider = create_provider(OPENAI_COMPATIBLE, model=options["model"], settings=settings, provider_options=options)
        result = provider.generate({
            "system_prompt": "Codex Writer provider health check.",
            "task_prompt": "Reply with the word OK.",
            "temperature": 0.0,
            "max_tokens": min(int(options.get("max_tokens") or 64), 64),
        })
        errors = _provider_failure_errors(result, "Provider returned empty health-check output")
        if errors:
            output_json("provider", ok=False, project_root=str(project_root),
                        data={"provider": public_runtime_status(project_root)}, errors=errors)
            return 5
        output_json("provider", data={
            "provider": public_runtime_status(project_root),
            "response_preview": result.get("text", "")[:80],
            "usage": result.get("usage", {}),
        }, project_root=str(project_root))
        return 0
    output_json("provider", ok=False, project_root=str(project_root),
                errors=[{"code": "INVALID_SUBCOMMAND", "message": "Use: provider presets|configure|status|test", "blocking": True}])
    return 2


def cmd_route_test(args):
    from pathlib import Path
    from codex_writer.agents.router import load_project_router, route_agent
    from codex_writer.agents.execution import resolve_agent_provider
    from codex_writer.agents.providers import is_external_provider
    project_root = Path(args.project_root).resolve()
    router = load_project_router(project_root)
    route = route_agent(router, args.agent)
    if args.provider:
        route = dict(route)
        route["provider"] = args.provider
    resolution = resolve_agent_provider(
        project_root,
        args.agent,
        provider_override=args.provider or "",
        require_external=False,
        input_kind=args.input_kind or "context_pack",
    )
    if resolution["errors"]:
        output_json("route_test", ok=False, project_root=str(project_root),
                    data={"agent": args.agent, "route": route}, errors=resolution["errors"])
        return resolution["exit_code"]
    output_json("route_test", data={
        "agent": args.agent,
        "route": route,
        "can_send_external": (not is_external_provider(route.get("provider", "codex"))) or not resolution["errors"],
        "provider_ready": True,
    }, project_root=str(project_root))
    return 0
def cmd_preflight(args):
    from pathlib import Path
    from codex_writer.runtime.health import check_mainline_health, check_projection_health
    project_root = Path(args.project_root).resolve()
    chapter = int(args.chapter) if args.chapter is not None else None
    health = check_mainline_health(
        project_root,
        chapter,
        require_foundation=_is_production(args) and chapter == 1,
    )
    if chapter is not None:
        proj_health = check_projection_health(project_root, chapter)
        health["projection_details"] = proj_health
    errors = []
    exit_code = 0 if health["mainline_ready"] else 3
    if _is_production(args):
        from codex_writer.agents.execution import production_preflight
        production = production_preflight(project_root)
        health["production"] = production
        errors.extend(production["errors"])
        if errors:
            health["mainline_ready"] = False
            exit_code = production["exit_code"]
    output_json("preflight", ok=health["mainline_ready"], data=health, errors=errors, project_root=str(project_root))
    return exit_code


def cmd_run_agent(args):
    from pathlib import Path
    from codex_writer.agents.router import load_project_router, route_agent
    from codex_writer.agents.prompts import build_agent_prompt
    from codex_writer.agents.agents import write_agent_run, create_agent_task
    from codex_writer.agents.execution import resolve_agent_provider
    from codex_writer.agents.providers import MockProvider

    project_root = Path(args.project_root).resolve()
    router = load_project_router(project_root)
    route = route_agent(router, args.agent)
    provider_name = args.provider or route["provider"]
    model_name = route["model"]

    task = create_agent_task(
        agent=args.agent,
        task_id=f"ch0001-{args.agent}-run_{__import__('datetime').datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        provider=provider_name,
        model=model_name
    )

    prompt = build_agent_prompt(args.agent, {"chapter": 1})

    input_text = json.dumps({"system_prompt": prompt["system_prompt"], "task_prompt": prompt["task_prompt"]}, ensure_ascii=False)
    output_text = ""

    if args.mock_output:
        provider = MockProvider(args.mock_output)
        result = provider.generate({"system_prompt": prompt["system_prompt"], "task_prompt": prompt["task_prompt"]})
        if result["error"]:
            task["status"] = "failed"
            task["errors"] = [{"code": "PROVIDER_FAILURE", "message": str(result["error"])}]
        else:
            task["status"] = "completed"
            task["output_ref"] = ".codex-writer/tmp/agent_output.json"
            if result["json"]:
                out_path = project_root / ".codex-writer" / "tmp" / "extraction_result.json"
                from codex_writer.core.io import write_json_atomic
                write_json_atomic(out_path, result["json"])
                task["output_ref"] = ".codex-writer/tmp/extraction_result.json"
            output_text = result.get("text", "")
    elif provider_name != "codex":
        resolution = resolve_agent_provider(
            project_root,
            args.agent,
            provider_override=args.provider or "",
            require_external=False,
            input_kind="context_pack",
            input_chars=len(input_text),
        )
        task["provider"] = resolution["provider"]
        task["model"] = resolution["model"]
        if resolution["errors"]:
            task["status"] = "failed"
            task["errors"] = resolution["errors"]
        else:
            result = resolution["provider_obj"].generate({
                "system_prompt": prompt["system_prompt"],
                "task_prompt": prompt["task_prompt"],
            })
            if result["error"]:
                task["status"] = "failed"
                task["errors"] = [{"code": "PROVIDER_FAILURE", "message": str(result["error"])}]
            else:
                task["status"] = "completed"
                task["usage"] = result.get("usage", {})
                output_text = result.get("text", "")
                out_path = project_root / ".codex-writer" / "tmp" / "agent_output.txt"
                from codex_writer.core.io import write_markdown_atomic
                write_markdown_atomic(out_path, output_text)
                task["output_ref"] = ".codex-writer/tmp/agent_output.txt"
    else:
        task["status"] = "completed"
        task["output_ref"] = ".codex-writer/tmp/agent_output.txt"

    record_path = write_agent_run(project_root, task, input_text=input_text, output_text=output_text)
    output_json("run_agent", ok=(task["status"] == "completed"),
                data={"agent": args.agent, "status": task["status"], "record": str(record_path)},
                errors=task.get("errors", []), project_root=str(project_root))
    return 0 if task["status"] == "completed" else 5


def cmd_references(args):
    from pathlib import Path
    from codex_writer.references.search import search_references
    project_root = Path(args.project_root).resolve()
    if args.ref_command == "search":
        results = search_references(project_root, args.query, top_k=args.top_k)
        output_json("references", data={"query": args.query, "results": results}, project_root=str(project_root))
        return 0
    output_json("references", ok=False, project_root=str(project_root),
                errors=[{"code": "INVALID_SUB", "message": "Use: references search --query <text>"}])
    return 2


def cmd_reading_power(args):
    from pathlib import Path
    from codex_writer.reading_power.tracker import get_open_debts, get_debt_summary
    project_root = Path(args.project_root).resolve()
    if args.rp_command == "debts":
        debts = get_open_debts(project_root)
        output_json("reading_power", data={"open_debts": debts}, project_root=str(project_root))
        return 0
    elif args.rp_command == "status":
        summary = get_debt_summary(project_root)
        output_json("reading_power", data=summary, project_root=str(project_root))
        return 0
    output_json("reading_power", data=get_debt_summary(project_root), project_root=str(project_root))
    return 0


def cmd_memory(args):
    from pathlib import Path
    from codex_writer.memory.scratchpad import (
        bootstrap,
        detect_conflicts,
        dump_memory,
        get_memory_stats,
        query_memory,
        update_memory_entry,
    )
    project_root = Path(args.project_root).resolve()
    if args.mem_command == "stats":
        stats = get_memory_stats(project_root)
        output_json("memory", data=stats, project_root=str(project_root))
        return 0
    elif args.mem_command == "query":
        results = query_memory(project_root, tag=args.tag)
        output_json("memory", data={"count": len(results), "results": results[:20]}, project_root=str(project_root))
        return 0
    elif args.mem_command == "bootstrap":
        data = bootstrap(project_root)
        output_json("memory", data={"bootstrapped": True, "episodic": len(data.get("episodic", [])), "semantic": len(data.get("semantic", []))}, project_root=str(project_root))
        return 0
    elif args.mem_command == "dump":
        output_json("memory", data=dump_memory(project_root), project_root=str(project_root))
        return 0
    elif args.mem_command == "conflicts":
        conflicts = detect_conflicts(project_root)
        output_json("memory", data={"count": len(conflicts), "results": conflicts}, project_root=str(project_root))
        return 0
    elif args.mem_command == "update":
        entry = update_memory_entry(
            project_root,
            args.id,
            status=args.status,
            content=args.content,
            tag=args.tag,
        )
        if entry is None:
            output_json(
                "memory",
                ok=False,
                project_root=str(project_root),
                errors=[{"code": "MEMORY_ENTRY_NOT_FOUND", "message": f"未找到记忆条目: {args.id}", "blocking": False}],
            )
            return 2
        output_json("memory", data={"entry": entry}, project_root=str(project_root))
        return 0
    output_json("memory", errors=[{"code": "INVALID_SUB", "message": "Use: memory stats|query|bootstrap|dump|conflicts|update"}])
    return 2


def cmd_learn(args):
    from pathlib import Path
    from codex_writer.memory.scratchpad import add_learn_entry
    project_root = Path(args.project_root).resolve()
    entry = add_learn_entry(project_root, args.content, tag=args.tag, chapter=args.chapter)
    output_json("learn", data={"id": entry["id"], "tag": args.tag, "chapter": args.chapter}, project_root=str(project_root))
    return 0


def cmd_dashboard(args):
    from pathlib import Path
    from codex_writer.dashboard import build_dashboard, format_dashboard_text, write_dashboard_html
    project_root = Path(args.project_root).resolve()
    data = build_dashboard(project_root)
    if args.format == "json":
        output_json("dashboard", data=data, project_root=str(project_root))
    elif args.format == "html":
        output_path = write_dashboard_html(project_root, data, output=args.output)
        print(f"Dashboard HTML: {output_path}")
    else:
        print(format_dashboard_text(data))
    return 0


def cmd_genres(args):
    from codex_writer.genres.templates import get_genre_template, list_genre_templates

    if args.genre_command == "list":
        templates = list_genre_templates()
        output_json("genres", data={"count": len(templates), "templates": templates})
        return 0
    if args.genre_command == "show":
        try:
            template = get_genre_template(args.genre)
        except KeyError:
            output_json(
                "genres",
                ok=False,
                errors=[{"code": "GENRE_TEMPLATE_NOT_FOUND", "message": f"未找到题材模板: {args.genre}", "blocking": False}],
            )
            return 2
        output_json("genres", data={"template": template})
        return 0
    output_json("genres", ok=False, errors=[{"code": "INVALID_SUB", "message": "Use: genres list|show"}])
    return 2


def cmd_use(args):
    from pathlib import Path
    from codex_writer.workspace import bind_active_project

    data = bind_active_project(Path(args.project_root))
    if not data.get("ok"):
        output_json("use", ok=False, data=data, errors=[data.get("error", {})])
        return 3
    output_json("use", data=data, project_root=data.get("active_project_root", ""))
    return 0


def cmd_where(args):
    from codex_writer.workspace import current_workspace

    data = current_workspace()
    output_json("where", ok=bool(data.get("active_project_root")), data=data, project_root=data.get("active_project_root", ""))
    return 0 if data.get("active_project_root") else 3


def cmd_resume(args):
    from pathlib import Path
    from codex_writer.workspace import resume_plan

    root = Path(args.project_root) if args.project_root else None
    data = resume_plan(root)
    if not data.get("ok"):
        output_json("resume", ok=False, data=data, errors=[data.get("error", {})])
        return 3
    output_json("resume", data=data, project_root=data.get("active_project_root", ""))
    return 0


def _apply_projections(project_root, chapter, commit, events_data):
    from codex_writer.commit.service import mark_projection_done
    from codex_writer.projections.state import update_state_from_commit
    from codex_writer.projections.summary import write_chapter_summary
    from codex_writer.projections.memory import update_memory_from_events
    from codex_writer.projections.index import update_index_from_commit
    from codex_writer.memory.scratchpad import update_from_commit as update_scratchpad
    from codex_writer.core.io import append_jsonl
    from codex_writer.core.locks import project_write_lock
    from datetime import datetime, timezone

    with project_write_lock(project_root):
        update_state_from_commit(project_root, commit)
        if commit["meta"]["status"] == "accepted":
            write_chapter_summary(project_root, chapter, commit)
            update_memory_from_events(project_root, chapter, events_data)
            update_index_from_commit(project_root, chapter, commit)
            update_scratchpad(project_root, chapter, commit)
            mark_projection_done(project_root, chapter, commit)
        log_path = project_root / ".codex-writer" / "logs" / "projections.jsonl"
        append_jsonl(log_path, {
            "time": datetime.now(timezone.utc).isoformat(),
            "chapter": chapter,
            "status": commit["meta"]["status"]
        })


def _register_subparsers(subparsers):
    sp_init = subparsers.add_parser("init", help="初始化书项目")
    sp_init.add_argument("--project-root", type=str, default=".")
    sp_init.add_argument("--title", type=str, default="")
    sp_init.add_argument("--genre", type=str, default="")
    sp_init.add_argument("--format", type=str, default="text")

    sp_use = subparsers.add_parser("use", help="绑定当前活跃写作项目")
    sp_use.add_argument("--project-root", type=str, required=True)
    sp_use.add_argument("--format", type=str, default="text")

    sp_where = subparsers.add_parser("where", help="查看当前活跃写作项目")
    sp_where.add_argument("--format", type=str, default="text")

    sp_resume = subparsers.add_parser("resume", help="恢复当前写作上下文并给出下一步")
    sp_resume.add_argument("--project-root", type=str, default="")
    sp_resume.add_argument("--format", type=str, default="text")

    sp_doctor = subparsers.add_parser("doctor", help="检查项目结构与依赖")
    sp_doctor.add_argument("--project-root", type=str, default=".")
    sp_doctor.add_argument("--strict", action="store_true")
    sp_doctor.add_argument("--chapter", type=str, default=None)
    sp_doctor.add_argument("--self-check", action="store_true")
    sp_doctor.add_argument("--format", type=str, default="text")

    sp_bible = subparsers.add_parser("bible", help="create, review, and approve the million-word novel bible")
    sp_bible.add_argument("--project-root", type=str, default=".")
    sub_bible = sp_bible.add_subparsers(dest="bible_command")
    sp_bible_create = sub_bible.add_parser("create")
    sp_bible_create.add_argument("--title", type=str, default="")
    sp_bible_create.add_argument("--genre", type=str, default="")
    sp_bible_create.add_argument("--target-words", type=int, default=1000000)
    sp_bible_create.add_argument("--target-chapters", type=int, default=500)
    sp_bible_create.add_argument("--volume-count", type=int, default=6)
    sp_bible_create.add_argument("--author-input", type=str, default="")
    sp_bible_create.add_argument("--demo", action="store_true")
    sp_bible_create.add_argument("--force", action="store_true")
    sp_bible_create.add_argument("--format", type=str, default="text")
    sp_bible_review = sub_bible.add_parser("review")
    sp_bible_review.add_argument("--format", type=str, default="text")
    sp_bible_status = sub_bible.add_parser("status")
    sp_bible_status.add_argument("--format", type=str, default="text")
    sp_bible_approve = sub_bible.add_parser("approve")
    sp_bible_approve.add_argument("--approved-by", type=str, default="author")
    sp_bible_approve.add_argument("--notes", type=str, default="")
    sp_bible_approve.add_argument("--format", type=str, default="text")

    sp_plan = subparsers.add_parser("plan", help="生成章节任务书")
    sp_plan.add_argument("--project-root", type=str, default=".")
    sp_plan.add_argument("--chapter", type=str, default="1")
    sp_plan.add_argument("--title", type=str, default="")
    sp_plan.add_argument("--production", action="store_true")
    sp_plan.add_argument("--demo", action="store_true")
    sp_plan.add_argument("--dry-run", action="store_true")
    sp_plan.add_argument("--format", type=str, default="text")

    sp_context = subparsers.add_parser("context", help="输出写前资料包")
    sp_context.add_argument("--project-root", type=str, default=".")
    sp_context.add_argument("--chapter", type=str, default="1")
    sp_context.add_argument("--format", type=str, default="text")

    sp_write = subparsers.add_parser("write", help="执行完整写章流程")
    sp_write.add_argument("--project-root", type=str, default=".")
    sp_write.add_argument("--chapter", type=str, default="1")
    sp_write.add_argument("--production", action="store_true")
    sp_write.add_argument("--demo", action="store_true")
    sp_write.add_argument("--no-backup", action="store_true")
    sp_write.add_argument("--format", type=str, default="text")

    sp_review = subparsers.add_parser("review", help="审查指定章节")
    sp_review.add_argument("--project-root", type=str, default=".")
    sp_review.add_argument("--chapter", type=str, default="1")
    sp_review.add_argument("--format", type=str, default="text")

    sp_extract = subparsers.add_parser("extract", help="抽取章节事实")
    sp_extract.add_argument("--project-root", type=str, default=".")
    sp_extract.add_argument("--chapter", type=str, default="1")
    sp_extract.add_argument("--production", action="store_true")
    sp_extract.add_argument("--demo", action="store_true")
    sp_extract.add_argument("--format", type=str, default="text")

    sp_commit = subparsers.add_parser("commit", help="生成并应用章节提交")
    sp_commit.add_argument("--project-root", type=str, default=".")
    sp_commit.add_argument("--chapter", type=str, default="1")
    sp_commit.add_argument("--no-backup", action="store_true")
    sp_commit.add_argument("--format", type=str, default="text")

    sp_query = subparsers.add_parser("query", help="查询人物、伏笔、设定、章节")
    sp_query.add_argument("--project-root", type=str, default=".")
    sp_query.add_argument("entity", nargs="?", default=None)
    sp_query.add_argument("--name", type=str, default=None)
    sp_query.add_argument("--format", type=str, default="text")

    sp_status = subparsers.add_parser("status", help="查看当前进度和最近提交")
    sp_status.add_argument("--project-root", type=str, default=".")
    sp_status.add_argument("--focus", type=str, default=None, choices=["memory", "rag", "all"])
    sp_status.add_argument("--format", type=str, default="text")

    sp_events = subparsers.add_parser("events", help="查询章节事件与事件链健康状态")
    sp_events.add_argument("--project-root", type=str, default=".")
    sp_events.add_argument("--chapter", type=str, default=None)
    sp_events.add_argument("--health", action="store_true")
    sp_events.add_argument("--format", type=str, default="text")

    sp_migrate = subparsers.add_parser("migrate", help="执行 schema 和数据库迁移")
    sp_migrate.add_argument("--project-root", type=str, default=".")
    sp_migrate.add_argument("--format", type=str, default="text")

    sp_backup = subparsers.add_parser("backup", help="创建项目级备份")
    sp_backup.add_argument("--project-root", type=str, default=".")
    sub_backup = sp_backup.add_subparsers(dest="sub_command")
    sp_backup_list = sub_backup.add_parser("list")
    sp_backup_list.add_argument("--project-root", type=str, default=".")
    sp_backup_list.add_argument("--format", type=str, default="text")
    sp_backup_verify = sub_backup.add_parser("verify")
    sp_backup_verify.add_argument("--project-root", type=str, default=".")
    sp_backup_verify.add_argument("--backup-id", type=str, required=True)
    sp_backup_verify.add_argument("--format", type=str, default="text")
    sp_backup.add_argument("--reason", type=str, default="手动备份")
    sp_backup.add_argument("--format", type=str, default="text")

    sp_restore = subparsers.add_parser("restore", help="从备份恢复到指定时间点")
    sp_restore.add_argument("--project-root", type=str, default=".")
    sp_restore.add_argument("--backup-id", type=str, required=True)
    sp_restore.add_argument("--format", type=str, default="text")

    sp_repair = subparsers.add_parser("repair", help="重建投影、索引或运行记录")
    sp_repair.add_argument("--project-root", type=str, default=".")
    sp_repair.add_argument("sub", choices=["projections", "index", "logs"])
    sp_repair.add_argument("--chapter", type=str, default=None)
    sp_repair.add_argument("--all", action="store_true", dest="action_all")
    sp_repair.add_argument("--from-commits", action="store_true", dest="action_from_commits")
    sp_repair.add_argument("--force", action="store_true")
    sp_repair.add_argument("--format", type=str, default="text")

    sp_agents = subparsers.add_parser("agents", help="查看子Agent路由、provider、隐私策略")
    sp_agents.add_argument("--project-root", type=str, default=".")
    sp_agents.add_argument("--format", type=str, default="text")

    sp_provider = subparsers.add_parser("provider", help="配置和测试 OpenAI-compatible 模型供应商")
    sp_provider.add_argument("--project-root", type=str, default=".")
    sp_provider.add_argument("--format", type=str, default="text")
    sub_provider = sp_provider.add_subparsers(dest="provider_subcommand")
    sp_provider_presets = sub_provider.add_parser("presets")
    sp_provider_presets.add_argument("--project-root", type=str, default=".")
    sp_provider_presets.add_argument("--format", type=str, default="text")
    sp_provider_configure = sub_provider.add_parser("configure")
    sp_provider_configure.add_argument("--preset", type=str, required=True, choices=["openai", "deepseek", "qwen", "custom"])
    sp_provider_configure.add_argument("--base-url", type=str, default="")
    sp_provider_configure.add_argument("--model", type=str, required=True)
    sp_provider_configure.add_argument("--timeout", type=float, default=None)
    sp_provider_configure.add_argument("--max-tokens", type=int, default=None)
    sp_provider_configure.add_argument("--format", type=str, default="text")
    sp_provider_status = sub_provider.add_parser("status")
    sp_provider_status.add_argument("--project-root", type=str, default=".")
    sp_provider_status.add_argument("--format", type=str, default="text")
    sp_provider_test = sub_provider.add_parser("test")
    sp_provider_test.add_argument("--preset", type=str, default="")
    sp_provider_test.add_argument("--base-url", type=str, default="")
    sp_provider_test.add_argument("--model", type=str, default="")
    sp_provider_test.add_argument("--timeout", type=float, default=None)
    sp_provider_test.add_argument("--max-tokens", type=int, default=None)
    sp_provider_test.add_argument("--format", type=str, default="text")

    sp_route_test = subparsers.add_parser("route-test", help="测试某类任务会路由到哪个 Agent 和模型")
    sp_route_test.add_argument("--project-root", type=str, default=".")
    sp_route_test.add_argument("--agent", type=str, required=True)
    sp_route_test.add_argument("--input-kind", type=str, default=None)
    sp_route_test.add_argument("--provider", type=str, default=None)
    sp_route_test.add_argument("--format", type=str, default="text")

    sp_run_agent = subparsers.add_parser("run-agent", help="内部命令：按协议运行单个 Agent")
    sp_run_agent.add_argument("--project-root", type=str, default=".")
    sp_run_agent.add_argument("--agent", type=str, required=True)
    sp_run_agent.add_argument("--provider", type=str, default=None)
    sp_run_agent.add_argument("--mock-output", type=str, default=None)
    sp_run_agent.add_argument("--format", type=str, default="text")

    sp_preflight = subparsers.add_parser("preflight", help="运行时健康检查")
    sp_preflight.add_argument("--project-root", type=str, default=".")
    sp_preflight.add_argument("--chapter", type=str, default=None)
    sp_preflight.add_argument("--production", action="store_true")
    sp_preflight.add_argument("--demo", action="store_true")
    sp_preflight.add_argument("--format", type=str, default="text")

    sp_genres = subparsers.add_parser("genres", help="查看和应用中文网文题材模板")
    sp_genres.add_argument("--format", type=str, default="text")
    sub_genres = sp_genres.add_subparsers(dest="genre_command")
    sp_genres_list = sub_genres.add_parser("list")
    sp_genres_list.add_argument("--format", type=str, default="text")
    sp_genres_show = sub_genres.add_parser("show")
    sp_genres_show.add_argument("--genre", type=str, required=True)
    sp_genres_show.add_argument("--format", type=str, default="text")

    sp_references = subparsers.add_parser("references", help="检索 references 知识库")
    sp_references.add_argument("--project-root", type=str, default=".")
    sub_ref = sp_references.add_subparsers(dest="ref_command")
    sp_ref_search = sub_ref.add_parser("search")
    sp_ref_search.add_argument("--project-root", type=str, default=".")
    sp_ref_search.add_argument("--query", type=str, required=True)
    sp_ref_search.add_argument("--top-k", type=int, default=10)
    sp_ref_search.add_argument("--format", type=str, default="text")

    sp_memory = subparsers.add_parser("memory", help="管理长期记忆")
    sp_memory.add_argument("--project-root", type=str, default=".")
    sub_mem = sp_memory.add_subparsers(dest="mem_command")
    sp_mem_stats = sub_mem.add_parser("stats")
    sp_mem_stats.add_argument("--project-root", type=str, default=".")
    sp_mem_stats.add_argument("--format", type=str, default="text")
    sp_mem_query = sub_mem.add_parser("query")
    sp_mem_query.add_argument("--project-root", type=str, default=".")
    sp_mem_query.add_argument("--tag", type=str, default="")
    sp_mem_query.add_argument("--format", type=str, default="text")
    sp_mem_bootstrap = sub_mem.add_parser("bootstrap")
    sp_mem_bootstrap.add_argument("--project-root", type=str, default=".")
    sp_mem_bootstrap.add_argument("--format", type=str, default="text")
    sp_mem_dump = sub_mem.add_parser("dump")
    sp_mem_dump.add_argument("--project-root", type=str, default=".")
    sp_mem_dump.add_argument("--format", type=str, default="text")
    sp_mem_conflicts = sub_mem.add_parser("conflicts")
    sp_mem_conflicts.add_argument("--project-root", type=str, default=".")
    sp_mem_conflicts.add_argument("--format", type=str, default="text")
    sp_mem_update = sub_mem.add_parser("update")
    sp_mem_update.add_argument("--project-root", type=str, default=".")
    sp_mem_update.add_argument("--id", type=str, required=True)
    sp_mem_update.add_argument("--status", type=str, default=None, choices=["active", "archived", "outdated", "contradicted", "tentative", "open", "resolved"])
    sp_mem_update.add_argument("--content", type=str, default=None)
    sp_mem_update.add_argument("--tag", type=str, default=None)
    sp_mem_update.add_argument("--format", type=str, default="text")

    sp_rp = subparsers.add_parser("reading-power", help="追读力管理")
    sp_rp.add_argument("--project-root", type=str, default=".")
    sub_rp = sp_rp.add_subparsers(dest="rp_command")
    sp_rp_debts = sub_rp.add_parser("debts")
    sp_rp_debts.add_argument("--project-root", type=str, default=".")
    sp_rp_debts.add_argument("--format", type=str, default="text")
    sp_rp_status = sub_rp.add_parser("status")
    sp_rp_status.add_argument("--project-root", type=str, default=".")
    sp_rp_status.add_argument("--format", type=str, default="text")

    sp_learn = subparsers.add_parser("learn", help="沉淀写作经验")
    sp_learn.add_argument("--project-root", type=str, default=".")
    sp_learn.add_argument("content", type=str, help="学习内容")
    sp_learn.add_argument("--tag", type=str, default="")
    sp_learn.add_argument("--chapter", type=int, default=0)
    sp_learn.add_argument("--format", type=str, default="text")

    sp_dashboard = subparsers.add_parser("dashboard", help="项目一站式观测面板")
    sp_dashboard.add_argument("--project-root", type=str, default=".")
    sp_dashboard.add_argument("--format", type=str, default="text")
    sp_dashboard.add_argument("--output", type=str, default=None)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="codex-writer", description="Codex Writer CLI")
    subparsers = parser.add_subparsers(dest="command")
    _register_subparsers(subparsers)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    cmd_map = {
        "init": cmd_init,
        "use": cmd_use,
        "where": cmd_where,
        "resume": cmd_resume,
        "doctor": cmd_doctor,
        "bible": cmd_bible,
        "plan": cmd_plan,
        "context": cmd_context,
        "write": cmd_write,
        "review": cmd_review,
        "extract": cmd_extract,
        "commit": cmd_commit_cli,
        "query": cmd_query,
        "status": cmd_status,
        "events": cmd_events,
        "migrate": cmd_migrate,
        "backup": cmd_backup,
        "restore": cmd_restore,
        "repair": cmd_repair,
        "agents": cmd_agents,
        "provider": cmd_provider,
        "route-test": cmd_route_test,
        "run-agent": cmd_run_agent,
        "preflight": cmd_preflight,
        "genres": cmd_genres,
        "references": cmd_references,
        "memory": cmd_memory,
        "reading-power": cmd_reading_power,
        "learn": cmd_learn,
        "dashboard": cmd_dashboard,
    }
    try:
        return cmd_map[args.command](args)
    except CodexWriterError as e:
        output_json(args.command, ok=False, errors=[_to_error_obj(e)])
        return e.exit_code
    except Exception as e:
        output_json(args.command, ok=False, errors=[{"code": "UNKNOWN_ERROR", "message": str(e), "blocking": False}])
        return 1


if __name__ == "__main__":
    sys.exit(main())
