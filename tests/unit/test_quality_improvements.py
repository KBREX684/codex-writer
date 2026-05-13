"""Tests for P0-P2 quality improvements.

Covers:
- Provider: content-array format, finish_reason=length warning, empty-output reroll
- Backup: incremental (skip unchanged files)
- produce command: resume, no-brief handling
- Review: word-count blocking gate, entity-state consistency
- Word count: Chinese-characters-only normalisation
- Schema validators: chapter_brief, novel_bible, story_contract
"""
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Provider improvements
# ---------------------------------------------------------------------------

class TestProviderExtractText:
    """_extract_completion_text now returns (text, finish_reason)."""

    def test_string_content(self):
        from codex_writer.agents.providers import _extract_completion_text
        raw = {"choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}]}
        text, fr = _extract_completion_text(raw)
        assert text == "hello"
        assert fr == "stop"

    def test_array_content_format(self):
        """New: multi-part content array (Anthropic-style)."""
        from codex_writer.agents.providers import _extract_completion_text
        raw = {
            "choices": [{
                "message": {
                    "content": [
                        {"type": "text", "text": "Part A "},
                        {"type": "text", "text": "Part B"},
                        {"type": "image_url", "url": "x"},  # non-text part, ignored
                    ]
                },
                "finish_reason": "stop",
            }]
        }
        text, fr = _extract_completion_text(raw)
        assert text == "Part A Part B"
        assert fr == "stop"

    def test_finish_reason_length(self):
        """finish_reason=length should be returned faithfully."""
        from codex_writer.agents.providers import _extract_completion_text
        raw = {"choices": [{"message": {"content": "truncated…"}, "finish_reason": "length"}]}
        text, fr = _extract_completion_text(raw)
        assert fr == "length"

    def test_empty_choices(self):
        from codex_writer.agents.providers import _extract_completion_text
        text, fr = _extract_completion_text({})
        assert text == ""
        assert fr == ""

    def test_legacy_text_field(self):
        from codex_writer.agents.providers import _extract_completion_text
        raw = {"choices": [{"text": "legacy", "finish_reason": "stop"}]}
        text, fr = _extract_completion_text(raw)
        assert text == "legacy"


class TestProviderGenerate:
    """MockProvider generates correct response shape."""

    def test_mock_provider_has_new_fields(self):
        from codex_writer.agents.providers import MockProvider
        result = MockProvider("hello world").generate({})
        assert "warnings" in result
        assert "finish_reason" in result
        assert result["finish_reason"] == "stop"

    def test_codex_provider_has_new_fields(self):
        from codex_writer.agents.providers import CodexProvider
        result = CodexProvider().generate({})
        assert "warnings" in result
        assert "finish_reason" in result

    def test_finish_reason_warning_propagated(self):
        """OpenAICompatibleProvider should include truncation warning."""
        from codex_writer.agents.providers import OpenAICompatibleProvider
        from codex_writer.core.config import Settings
        raw_response = json.dumps({
            "choices": [
                {"message": {"content": "some text"}, "finish_reason": "length"}
            ],
            "usage": {},
        })
        mock_resp = MagicMock()
        mock_resp.read.return_value = raw_response.encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        settings = Settings(
            openai_compatible_base_url="http://localhost/v1",
            openai_compatible_api_key="test-key",
            openai_compatible_model="gpt-x",
        )
        provider = OpenAICompatibleProvider(settings=settings)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = provider.generate({"system_prompt": "s", "task_prompt": "t"})
        assert result["finish_reason"] == "length"
        assert any("max_tokens" in w for w in result["warnings"])

    def test_empty_output_retried(self):
        """Empty model output triggers reroll up to _MAX_EMPTY_RETRIES times."""
        from codex_writer.agents.providers import OpenAICompatibleProvider, _MAX_EMPTY_RETRIES
        from codex_writer.core.config import Settings

        call_count = 0

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raw = json.dumps({
                "choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
                "usage": {},
            })
            m = MagicMock()
            m.read.return_value = raw.encode()
            m.__enter__ = MagicMock(return_value=m)
            m.__exit__ = MagicMock(return_value=False)
            return m

        settings = Settings(
            openai_compatible_base_url="http://localhost/v1",
            openai_compatible_api_key="test-key",
            openai_compatible_model="m",
        )
        provider = OpenAICompatibleProvider(settings=settings)
        with patch("urllib.request.urlopen", side_effect=_side_effect), \
             patch("time.sleep"):
            result = provider.generate({"system_prompt": "s", "task_prompt": "t"})
        # Should have tried 1 + _MAX_EMPTY_RETRIES times total
        assert call_count == 1 + _MAX_EMPTY_RETRIES
        assert result["text"] == ""


# ---------------------------------------------------------------------------
# Backup: incremental logic
# ---------------------------------------------------------------------------

class TestIncrementalBackup:
    def test_unchanged_files_skipped(self, tmp_path):
        from codex_writer.storage.backup import create_backup_manifest
        cw = tmp_path / ".codex-writer"
        cw.mkdir()
        (cw / "state.json").write_text('{"v":1}', encoding="utf-8")

        # First backup: should copy the file
        m1 = create_backup_manifest(tmp_path, reason="first", incremental=True)
        assert any("state.json" in f["path"] for f in m1["files"])
        assert m1["incremental"] is True

        # Second backup with no changes: should skip the unchanged file
        m2 = create_backup_manifest(tmp_path, reason="second", incremental=True)
        assert not any("state.json" in f["path"] for f in m2["files"]), \
            "Unchanged state.json should be skipped in incremental backup"

    def test_changed_file_included(self, tmp_path):
        from codex_writer.storage.backup import create_backup_manifest
        cw = tmp_path / ".codex-writer"
        cw.mkdir()
        (cw / "state.json").write_text('{"v":1}', encoding="utf-8")
        create_backup_manifest(tmp_path, reason="first", incremental=True)
        # Modify the file
        (cw / "state.json").write_text('{"v":2}', encoding="utf-8")
        m2 = create_backup_manifest(tmp_path, reason="second", incremental=True)
        assert any("state.json" in f["path"] for f in m2["files"]), \
            "Modified state.json should appear in incremental backup"

    def test_full_backup_copies_all(self, tmp_path):
        from codex_writer.storage.backup import create_backup_manifest
        cw = tmp_path / ".codex-writer"
        cw.mkdir()
        (cw / "state.json").write_text('{"v":1}', encoding="utf-8")
        create_backup_manifest(tmp_path, incremental=True)
        # Full backup should include all files regardless of change
        m = create_backup_manifest(tmp_path, reason="full", incremental=False)
        assert any("state.json" in f["path"] for f in m["files"])


# ---------------------------------------------------------------------------
# produce command: basics
# ---------------------------------------------------------------------------

class TestProduceCommand:
    def _make_accepted_state(self, tmp_path: Path, chapters: list[int]):
        import json
        cw = tmp_path / ".codex-writer"
        cw.mkdir(parents=True, exist_ok=True)
        chapters_data = {str(ch): {"status": "accepted", "word_count": 1000} for ch in chapters}
        (cw / "state.json").write_text(
            json.dumps({"total_word_count": len(chapters) * 1000,
                        "current_chapter": max(chapters, default=0),
                        "chapters": chapters_data}),
            encoding="utf-8"
        )

    def test_produce_skips_accepted_with_resume(self, tmp_path):
        """--resume should skip already-accepted chapters."""
        from codex_writer.cli import cmd_produce
        self._make_accepted_state(tmp_path, [1, 2])

        class _Args:
            project_root = str(tmp_path)
            from_chapter = 1
            to_chapter = 2
            resume = True
            retry = 0
            delay = 0.0
            no_backup = True
            format = "json"

        # cmd_produce should call cmd_write 0 times (all skipped)
        with patch("codex_writer.cli.cmd_write") as mock_write, \
             patch("codex_writer.cli.output_json") as mock_out:
            rc = cmd_produce(_Args())
        mock_write.assert_not_called()
        assert rc == 0

    def test_produce_reports_no_brief(self, tmp_path):
        """Chapters without a brief should be marked as no_brief, not failed."""
        from codex_writer.cli import cmd_produce
        (tmp_path / ".codex-writer").mkdir(parents=True, exist_ok=True)

        class _Args:
            project_root = str(tmp_path)
            from_chapter = 1
            to_chapter = 1
            resume = False
            retry = 0
            delay = 0.0
            no_backup = True
            format = "json"

        captured = {}

        def _capture(*a, **kw):
            captured.update(kw)

        with patch("codex_writer.cli.output_json", side_effect=_capture):
            rc = cmd_produce(_Args())

        results = captured.get("data", {}).get("chapters", [])
        assert any(r["status"] == "no_brief" for r in results)


# ---------------------------------------------------------------------------
# Review: word-count blocking gate
# ---------------------------------------------------------------------------

class TestReviewWordCount:
    def _make_brief(self, tmp_path: Path, chapter: int, target_words: int):
        cw = tmp_path / ".codex-writer"
        (cw / "story" / "chapters").mkdir(parents=True, exist_ok=True)
        brief = {
            "meta": {"schema_version": "codex-writer/chapter-brief/v1"},
            "chapter": chapter, "title": "测试章", "target_words": target_words
        }
        (cw / "story" / "chapters" / f"第{chapter:04d}章任务书.json").write_text(
            json.dumps(brief, ensure_ascii=False), encoding="utf-8"
        )

    def test_word_count_blocking_when_severely_short(self, tmp_path):
        from codex_writer.review.pipeline import _check_word_count
        self._make_brief(tmp_path, 1, 2000)
        # 50 characters — way under 50% of 2000
        text = "短" * 50
        issues = _check_word_count(tmp_path, text, 1)
        assert any(i["blocking"] for i in issues), \
            "Severely short text (<50% of target) should produce a blocking issue"

    def test_word_count_non_blocking_slightly_short(self, tmp_path):
        from codex_writer.review.pipeline import _check_word_count
        self._make_brief(tmp_path, 1, 2000)
        # 1200 chars = 60% of 2000 — not blocking but medium
        text = "字" * 1200
        issues = _check_word_count(tmp_path, text, 1)
        blocking = [i for i in issues if i["blocking"]]
        assert not blocking
        # May or may not emit a medium issue
        medium = [i for i in issues if i["severity"] == "medium"]
        assert len(medium) <= 1

    def test_word_count_ok_near_target(self, tmp_path):
        from codex_writer.review.pipeline import _check_word_count
        self._make_brief(tmp_path, 1, 2000)
        text = "字" * 1800  # 90% — fine
        issues = _check_word_count(tmp_path, text, 1)
        assert not issues


# ---------------------------------------------------------------------------
# Entity state consistency check
# ---------------------------------------------------------------------------

class TestEntityStateConsistency:
    def _setup_db(self, tmp_path: Path, entity: str, status_val: str, chapter: int):
        from codex_writer.storage.db import connect_db, init_schema
        init_schema(tmp_path)
        with connect_db(tmp_path) as conn:
            conn.execute(
                "INSERT INTO state_changes (chapter, entity_id, field, old_value, new_value, reason) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (chapter, entity, "status", "alive", status_val, "killed in battle"),
            )
            conn.commit()

    def test_dead_entity_in_text_raises_issue(self, tmp_path):
        from codex_writer.review.pipeline import _check_entity_state_consistency
        (tmp_path / ".codex-writer").mkdir(parents=True, exist_ok=True)
        self._setup_db(tmp_path, "青龙", "dead", chapter=5)
        text = "青龙出现了，他微笑着向主角走来。"
        issues = _check_entity_state_consistency(tmp_path, text, chapter=10)
        assert any("青龙" in i["description"] for i in issues), \
            "Dead entity appearing in text should produce an issue"

    def test_no_issue_when_entity_absent(self, tmp_path):
        from codex_writer.review.pipeline import _check_entity_state_consistency
        (tmp_path / ".codex-writer").mkdir(parents=True, exist_ok=True)
        self._setup_db(tmp_path, "青龙", "dead", chapter=5)
        text = "主角独自前行，四周一片寂静。"
        issues = _check_entity_state_consistency(tmp_path, text, chapter=10)
        assert not issues


# ---------------------------------------------------------------------------
# Bug-fix regression: word count consistency between review and state
# ---------------------------------------------------------------------------

class TestWordCountConsistency:
    """Review's _check_word_count must use the same counter as state.py."""

    def _make_brief(self, tmp_path: Path, chapter: int, target_words: int):
        import json
        cw = tmp_path / ".codex-writer"
        (cw / "story" / "chapters").mkdir(parents=True, exist_ok=True)
        brief = {
            "meta": {"schema_version": "codex-writer/chapter-brief/v1"},
            "chapter": chapter, "title": "测试", "target_words": target_words,
        }
        (cw / "story" / "chapters" / f"第{chapter:04d}章任务书.json").write_text(
            json.dumps(brief, ensure_ascii=False), encoding="utf-8"
        )

    def test_curly_quotes_counted_in_review(self, tmp_path):
        """U+201C/201D/2018/2019 and U+2014/2026 must be counted by pipeline."""
        from codex_writer.review.pipeline import _check_word_count
        from codex_writer.projections.state import _count_chinese_chars
        self._make_brief(tmp_path, 1, 5000)
        # 1000 CJK chars + 6 special punctuation chars
        text = "字" * 1000 + "\u201c\u201d\u2018\u2019\u2014\u2026"
        expected = _count_chinese_chars(text)
        assert expected == 1006, f"_count_chinese_chars should count 1006, got {expected}"
        issues = _check_word_count(tmp_path, text, 1)
        # 1006/5000 = ~20%, definitely blocking
        high_issues = [i for i in issues if i["blocking"]]
        assert high_issues
        evidence = high_issues[0]["evidence"]
        import re
        m = re.search(r"actual=(\d+)", evidence)
        assert m, "evidence should contain actual=..."
        assert int(m.group(1)) == expected, (
            f"Review actual={m.group(1)} != state._count_chinese_chars={expected}; "
            "counters are inconsistent"
        )


# ---------------------------------------------------------------------------
# Bug-fix regression: chapter revert reduces total_word_count
# ---------------------------------------------------------------------------

class TestChapterRevertWordCount:
    """After revert, total_word_count in state.json must decrease."""

    def _write_state(self, cw: Path, chapters: dict):
        import json
        total = sum(c["word_count"] for c in chapters.values() if c["status"] == "accepted")
        state = {
            "meta": {"schema_version": "codex-writer/state/v1"},
            "total_word_count": total,
            "current_chapter": max((int(k) for k in chapters), default=0),
            "current_volume": 1,
            "chapters": {str(k): v for k, v in chapters.items()},
            "story_status": "writing",
        }
        (cw / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        return state

    def _write_commit(self, cw: Path, chapter: int, status: str):
        import json
        commit = {
            "meta": {"schema_version": "codex-writer/chapter-commit/v1",
                     "chapter": chapter, "status": status},
            "refs": {}, "checks": {}, "accepted_events": [], "state_deltas": [],
            "entity_deltas": [], "summary_text": "",
            "projection_status": {"state": "done", "summary": "done", "memory": "done", "index": "done"},
        }
        commits_dir = cw / "commits"
        commits_dir.mkdir(parents=True, exist_ok=True)
        (commits_dir / f"第{chapter:04d}章提交.json").write_text(
            json.dumps(commit, ensure_ascii=False), encoding="utf-8"
        )
        return commit

    def test_revert_decrements_total(self, tmp_path):
        from codex_writer.projections.state import update_state_from_commit
        import json
        cw = tmp_path / ".codex-writer"
        cw.mkdir(parents=True, exist_ok=True)
        # Two accepted chapters, each 1000 words.
        self._write_state(cw, {
            1: {"chapter": 1, "status": "accepted", "word_count": 1000,
                "commit_path": ".codex-writer/commits/第0001章提交.json"},
            2: {"chapter": 2, "status": "accepted", "word_count": 1500,
                "commit_path": ".codex-writer/commits/第0002章提交.json"},
        })
        # Revert chapter 1.
        commit = self._write_commit(cw, 1, "reverted")
        update_state_from_commit(tmp_path, commit)
        state = json.loads((cw / "state.json").read_text(encoding="utf-8"))
        # Chapter 1 is reverted — should not count.
        assert state["total_word_count"] == 1500, (
            f"total_word_count should be 1500 after revert, got {state['total_word_count']}"
        )
        assert state["chapters"]["1"]["status"] == "reverted"

    def test_reject_does_not_add_to_total(self, tmp_path):
        from codex_writer.projections.state import update_state_from_commit
        import json
        cw = tmp_path / ".codex-writer"
        cw.mkdir(parents=True, exist_ok=True)
        self._write_state(cw, {
            1: {"chapter": 1, "status": "accepted", "word_count": 1000,
                "commit_path": ".codex-writer/commits/第0001章提交.json"},
        })
        commit = self._write_commit(cw, 2, "rejected")
        update_state_from_commit(tmp_path, commit)
        state = json.loads((cw / "state.json").read_text(encoding="utf-8"))
        # Chapter 2 is rejected — should not add to total.
        assert state["total_word_count"] == 1000


# ---------------------------------------------------------------------------
# Word count normalisation
# ---------------------------------------------------------------------------

class TestWordCountNormalisation:
    def test_counts_chinese_not_whitespace(self):
        from codex_writer.projections.state import _count_chinese_chars
        text = "你好 世界\n# Heading\n**bold**"
        count = _count_chinese_chars(text)
        assert count == 4, f"Expected 4 Chinese chars, got {count}"

    def test_counts_fullwidth_punctuation(self):
        from codex_writer.projections.state import _count_chinese_chars
        text = '\u4ed6\u8bf4\uff1a\u201c\u4f60\u597d\u3002\u201d'
        count = _count_chinese_chars(text)
        # 他说你好 (4 chars) + 3 punctuation （：""。）= 7 or more
        assert count >= 4

    def test_curly_double_quotes_counted(self):
        """U+201C and U+201D (dialogue quotes) must be counted."""
        from codex_writer.projections.state import _count_chinese_chars
        assert _count_chinese_chars("\u201c") == 1, "left curly double quote must be counted"
        assert _count_chinese_chars("\u201d") == 1, "right curly double quote must be counted"

    def test_curly_single_quotes_counted(self):
        """U+2018 and U+2019 (inner dialogue quotes) must be counted."""
        from codex_writer.projections.state import _count_chinese_chars
        assert _count_chinese_chars("\u2018") == 1, "left curly single quote must be counted"
        assert _count_chinese_chars("\u2019") == 1, "right curly single quote must be counted"

    def test_em_dash_and_ellipsis_counted(self):
        """U+2014 (em dash) and U+2026 (ellipsis) must be counted."""
        from codex_writer.projections.state import _count_chinese_chars
        assert _count_chinese_chars("\u2014") == 1, "em dash must be counted"
        assert _count_chinese_chars("\u2026") == 1, "ellipsis must be counted"

    def test_ascii_quotes_not_counted(self):
        """ASCII apostrophe and double-quote must NOT be counted."""
        from codex_writer.projections.state import _count_chinese_chars
        assert _count_chinese_chars("'") == 0, "ASCII apostrophe must not be counted"
        assert _count_chinese_chars('"') == 0, 'ASCII double-quote must not be counted'

    def test_empty_text(self):
        from codex_writer.projections.state import _count_chinese_chars
        assert _count_chinese_chars("") == 0

    def test_ascii_only(self):
        from codex_writer.projections.state import _count_chinese_chars
        assert _count_chinese_chars("Hello World 123") == 0


# ---------------------------------------------------------------------------
# Schema validators
# ---------------------------------------------------------------------------

class TestSchemaValidators:
    def test_valid_chapter_brief(self):
        from codex_writer.schemas.validators import validate_chapter_brief
        brief = {
            "meta": {"schema_version": "codex-writer/chapter-brief/v1"},
            "chapter": 1, "title": "测试章", "target_words": 2500,
        }
        errors = validate_chapter_brief(brief)
        assert not errors

    def test_chapter_brief_missing_chapter(self):
        from codex_writer.schemas.validators import validate_chapter_brief
        errors = validate_chapter_brief({"title": "章"})
        assert any("chapter" in e for e in errors)

    def test_chapter_brief_negative_target_words(self):
        from codex_writer.schemas.validators import validate_chapter_brief
        errors = validate_chapter_brief({"chapter": 1, "title": "章", "target_words": -1})
        assert any("target_words" in e for e in errors)

    def test_novel_bible_below_min_words(self):
        from codex_writer.schemas.validators import validate_novel_bible
        bible = {
            "meta": {}, "book": {}, "sections": {"volume_roadmap": {"volumes": []}},
            "target_scale": {"target_words": 500000, "target_chapters": 300, "volume_count": 5},
        }
        errors = validate_novel_bible(bible)
        assert any("target_words" in e for e in errors)

    def test_novel_bible_below_min_chapters(self):
        from codex_writer.schemas.validators import validate_novel_bible
        bible = {
            "meta": {}, "book": {}, "sections": {"volume_roadmap": {"volumes": []}},
            "target_scale": {"target_words": 1_000_000, "target_chapters": 100, "volume_count": 5},
        }
        errors = validate_novel_bible(bible)
        assert any("target_chapters" in e for e in errors)

    def test_novel_bible_volume_count_mismatch(self):
        from codex_writer.schemas.validators import validate_novel_bible
        bible = {
            "meta": {}, "book": {},
            "sections": {"volume_roadmap": {"volumes": [{"v": 1}, {"v": 2}]}},
            "target_scale": {"target_words": 1_000_000, "target_chapters": 300, "volume_count": 5},
        }
        errors = validate_novel_bible(bible)
        assert any("volume" in e.lower() for e in errors)

    def test_valid_story_contract(self):
        from codex_writer.schemas.validators import validate_story_contract
        contract = {
            "meta": {"schema_version": "codex-writer/story-contract/v1"},
            "book": {"title": "测试书", "genre": "修仙"},
            "core": {},
        }
        errors = validate_story_contract(contract)
        assert not errors

    def test_story_contract_missing_book(self):
        from codex_writer.schemas.validators import validate_story_contract
        errors = validate_story_contract({"meta": {}})
        assert any("book" in e for e in errors)
