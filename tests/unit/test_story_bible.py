import copy

from codex_writer.story.bible import (
    create_demo_bible,
    create_novel_bible_template,
    validate_novel_bible,
)


def test_blank_novel_bible_template_requires_million_word_content_and_approval():
    bible = create_novel_bible_template("大恨仙尊", "玄幻")

    report = validate_novel_bible(bible)

    assert report["ready"] is False
    assert report["content_ready"] is False
    assert "approval.status" in report["missing"]
    assert "sections.project_positioning.reader_promise" in report["missing"]
    assert "sections.volume_roadmap.volumes" in report["missing"]


def test_demo_novel_bible_is_content_ready_but_not_approved():
    bible = create_demo_bible("大恨仙尊", "玄幻", target_words=1_000_000, target_chapters=500)

    draft_report = validate_novel_bible(bible)
    approved = copy.deepcopy(bible)
    approved["approval"]["status"] = "approved"
    approved_report = validate_novel_bible(approved)

    assert draft_report["content_ready"] is True
    assert draft_report["ready"] is False
    assert draft_report["missing"] == ["approval.status"]
    assert approved_report["ready"] is True
    assert approved_report["missing"] == []


def test_novel_bible_rejects_short_scale_even_when_sections_exist():
    bible = create_demo_bible("短篇", "玄幻", target_words=300_000, target_chapters=120)
    bible["approval"]["status"] = "approved"

    report = validate_novel_bible(bible)

    assert report["ready"] is False
    assert "target_scale.target_words>=1000000" in report["missing"]
    assert "target_scale.target_chapters>=300" in report["missing"]
