import re
from pathlib import Path

from codex_writer.core.io import read_json, write_json_atomic
from codex_writer.core.paths import chapter_brief_path, extraction_result_path, chapter_md_path


def extract_from_chapter(project_root: Path, chapter: int, chapter_text: str = "") -> dict:
    brief_path = chapter_brief_path(project_root, chapter)
    title = ""
    must_cover = []
    key_entities = []
    if brief_path.exists():
        brief = read_json(brief_path)
        title = brief.get("title", "")
        must_cover = brief.get("must_cover_nodes", [])
        key_entities = brief.get("key_entities", [])

    md_path = chapter_md_path(project_root, chapter, title)
    if not chapter_text and md_path.exists():
        chapter_text = md_path.read_text(encoding="utf-8")

    covered_nodes = [node for node in must_cover if node in chapter_text]
    missed_nodes = [node for node in must_cover if node not in chapter_text]

    found_entities = [e for e in key_entities if e in chapter_text]
    entity_deltas = [{"entity": e, "chapter": chapter, "mentioned": True} for e in found_entities]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", chapter_text) if p.strip()]
    scenes = []
    for i, para_group in enumerate(paragraphs):
        if len(para_group) > 10:
            scenes.append({"index": i + 1, "text_preview": para_group[:80]})

    summary = chapter_text.strip()[:200] if chapter_text else ""

    dominant = ""
    if found_entities:
        from collections import Counter
        entity_counts = Counter()
        for entity in key_entities:
            entity_counts[entity] = chapter_text.count(entity)
        dominant = entity_counts.most_common(1)[0][0] if entity_counts else ""

    result = {
        "meta": {"schema_version": "codex-writer/extraction-result/v1"},
        "chapter": chapter,
        "covered_nodes": covered_nodes,
        "missed_nodes": missed_nodes,
        "pending_disambiguation": [],
        "state_deltas": [],
        "entity_deltas": entity_deltas,
        "accepted_events": [],
        "scenes": scenes,
        "summary_text": summary,
        "dominant_thread": dominant
    }

    output_path = extraction_result_path(project_root, chapter)
    write_json_atomic(output_path, result)

    return result
