import json

from codex_writer.extraction.extractor import extract_from_chapter
from codex_writer.extraction.schemas import validate_extraction_result


def test_extraction_generates_entities_appeared(tmp_path):
    project = tmp_path / "book"
    (project / ".codex-writer" / "story" / "chapters").mkdir(parents=True)
    brief = project / ".codex-writer" / "story" / "chapters" / "第0001章任务书.json"
    brief.write_text(json.dumps({
        "meta": {"schema_version": "codex-writer/chapter-brief/v1"},
        "chapter": 1, "title": "入局",
        "key_entities": ["萧衡", "黑水城"]
    }, ensure_ascii=False), encoding="utf-8")

    (project / "正文").mkdir()
    (project / "正文" / "第0001章-入局.md").write_text("萧衡前往黑水城。", encoding="utf-8")

    result = extract_from_chapter(project, 1)
    assert len(result["entities_appeared"]) >= 1
    assert result["entities_appeared"][0]["entity"] in ("萧衡", "黑水城")
    assert isinstance(result["accepted_events"], list)
    assert len(result["accepted_events"]) > 0


def test_extraction_schema_validates_entities_appeared():
    result = {"meta": {"schema_version": "codex-writer/extraction-result/v1"}, "chapter": 1,
              "accepted_events": [], "summary_text": "test", "entities_appeared": "not-a-list"}
    errors = validate_extraction_result(result)
    assert any("entities_appeared" in e for e in errors)
