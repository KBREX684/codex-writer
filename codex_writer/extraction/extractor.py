import re
from collections import Counter
from pathlib import Path

from codex_writer.core.io import read_json, write_json_atomic
from codex_writer.core.paths import chapter_brief_path, extraction_result_path, chapter_md_path

MIN_PARAGRAPH_LEN = 10
# Target total chars for the structured summary
SUMMARY_TARGET_CHARS = 300

# Heuristic scene-break signals (location/time/POV shifts)
_SCENE_BREAK_SIGNALS = [
    r"(?:翌日|次日|翌晨|翌夜|隔日|数日后|一日后|数月后)",
    r"(?:与此同时|另一边|另一处|彼时)",
    r"(?:。\s*\n\s*\n|！\s*\n\s*\n|？\s*\n\s*\n)",   # blank-line after sentence ending
    r"(?:——|\*\s*\*\s*\*)",                            # explicit break marker
    r"(?:离开了|来到了|赶往|回到).{0,10}(?:，|。)",
]

# Candidate new-entity name patterns (2–6 Chinese chars, title-case context)
_ENTITY_CANDIDATE_PATTERN = re.compile(
    r"(?:(?:一位|这位|那位|此人|一名|这名|那名)\s*)([\u4e00-\u9fff]{2,6})"
    r"|(?:名叫|叫做|叫作|称为|唤作)\s*([\u4e00-\u9fff]{2,6})"
    r"|([\u4e00-\u9fff]{2,4})(?:功法|剑法|刀法|掌法|诀|经|典|术|法则|禁地|宗|门|族|殿|阁|峰|山|城|界|域)"
)

# Patterns to detect opening hook, main conflict, payoff, and ending hook
_OPENING_PATTERNS = [r"(?:突然|忽然|陡然|猛然)", r"[？?！!…]", r"(?:危险|威胁|来袭|杀机)"]
_CONFLICT_PATTERNS = [r"(?:对峙|交手|争夺|质问|逼问|阻拦)", r"(?:战斗|搏斗|比拼|较量)"]
_PAYOFF_PATTERNS = [
    r"(?:突破|晋升|踏入|升入|晋级)",
    r"(?:反转|逆转|打脸|震惊|揭露|暴露)",
    r"(?:击败|击倒|碾压|秒杀)",
]
_HOOK_PATTERNS = [
    r"(?:却不知|殊不知|谁也没想到)",
    r"(?:忽然|突然|陡然).{0,20}(?:响起|出现|袭来|传来)",
    r"(?:危险|威胁|杀机).{0,10}(?:逼近|降临|显现)",
    r"[？?]{1,}$",
]


def _detect_scenes(paragraphs: list[str]) -> list[dict]:
    """Split paragraphs into scenes using heuristic break signals."""
    if not paragraphs:
        return []

    scenes: list[dict] = []
    current: list[str] = []
    compiled = [re.compile(p) for p in _SCENE_BREAK_SIGNALS]

    for i, para in enumerate(paragraphs):
        is_break = i > 0 and any(c.search(para) for c in compiled[:2])  # time/POV shift signals
        # blank-line break is already handled by paragraph splitting; check explicit markers
        if not is_break and i > 0:
            is_break = bool(re.search(r"——|\*\s*\*\s*\*", para))

        if is_break and current:
            scenes.append({
                "index": len(scenes) + 1,
                "text_preview": current[0][:80],
                "paragraph_count": len(current),
            })
            current = [para]
        else:
            current.append(para)

    if current:
        scenes.append({
            "index": len(scenes) + 1,
            "text_preview": current[0][:80],
            "paragraph_count": len(current),
        })

    return scenes


def _find_new_entity_candidates(chapter_text: str, known_entities: list[str]) -> list[dict]:
    """Return candidate new entities not in the known list."""
    known_set = set(known_entities)
    found: dict[str, str] = {}
    for m in _ENTITY_CANDIDATE_PATTERN.finditer(chapter_text):
        name = next((g for g in m.groups() if g), None)
        if name and name not in known_set and name not in found:
            # Determine rough type from context
            ctx = chapter_text[max(0, m.start() - 10): m.end() + 10]
            if any(suffix in name or suffix in ctx for suffix in ["功法", "剑法", "刀法", "掌法", "诀", "经", "典", "术", "法则"]):
                etype = "skill"
            elif any(suffix in name or suffix in ctx for suffix in ["宗", "门", "族", "殿", "阁", "峰", "山", "城", "界", "域", "禁地"]):
                etype = "location_or_faction"
            else:
                etype = "character_candidate"
            found[name] = etype

    return [{"name": n, "type": t, "description": ""} for n, t in found.items()]


def _build_structured_summary(
    chapter_text: str,
    paragraphs: list[str],
    title: str,
    chapter: int,
) -> str:
    """Build a 5-part structured summary: 目标·推进·冲突·兑现·钩子."""
    if not paragraphs:
        return ""

    total = len(paragraphs)
    first_quarter = paragraphs[: max(1, total // 4)]
    mid = paragraphs[total // 4: 3 * total // 4]
    last_quarter = paragraphs[max(0, 3 * total // 4):]
    tail_two = paragraphs[-2:] if len(paragraphs) >= 2 else paragraphs[-1:]

    def _find_snippet(paras: list[str], patterns: list[str], max_chars: int = 60) -> str:
        compiled = [re.compile(p) for p in patterns]
        for para in paras:
            for c in compiled:
                if c.search(para):
                    return para[:max_chars]
        return paras[0][:max_chars] if paras else ""

    goal = _find_snippet(first_quarter, _OPENING_PATTERNS)
    conflict = _find_snippet(mid, _CONFLICT_PATTERNS)
    payoff = _find_snippet(mid + last_quarter, _PAYOFF_PATTERNS)
    hook = _find_snippet(tail_two, _HOOK_PATTERNS)
    push = mid[len(mid) // 2][:60] if mid else (paragraphs[total // 2][:60] if paragraphs else "")

    parts = [
        f"【目标】{goal}",
        f"【推进】{push}",
        f"【冲突】{conflict}",
        f"【兑现】{payoff}",
        f"【钩子】{hook}",
    ]
    return "；".join(p for p in parts if p.split("】", 1)[-1].strip())


def extract_from_chapter(project_root: Path, chapter: int, chapter_text: str = "") -> dict:
    brief_path = chapter_brief_path(project_root, chapter)
    title = ""
    must_cover: list[str] = []
    key_entities: list[str] = []
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

    entities_appeared = []
    entity_counts = Counter()
    for entity in key_entities:
        if entity in chapter_text:
            positions = [m.start() for m in re.finditer(re.escape(entity), chapter_text)]
            entity_counts[entity] = len(positions)
            entities_appeared.append({
                "entity": entity,
                "count": len(positions),
                "first_position": positions[0] if positions else 0,
            })

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", chapter_text) if p.strip() and len(p.strip()) > MIN_PARAGRAPH_LEN]

    # Improved scene detection using heuristic signals
    scenes = _detect_scenes(paragraphs)

    # Build events
    accepted_events = []
    for entity in entities_appeared:
        accepted_events.append({
            "event_id": f"ch{chapter:04d}-entity-appeared-{entity['entity']}",
            "chapter": chapter,
            "event_type": "entity_mentioned",
            "subject": entity["entity"],
            "payload": {"count": entity["count"], "first_position": entity["first_position"]},
        })

    for i, scene in enumerate(scenes[:-1]):
        accepted_events.append({
            "event_id": f"ch{chapter:04d}-scene-boundary-{i + 1}",
            "chapter": chapter,
            "event_type": "scene_boundary",
            "subject": f"场景{i + 1}→场景{i + 2}",
            "payload": {"from_scene": i + 1, "to_scene": i + 2},
        })

    # Structured 5-part summary replaces naive text truncation
    summary = _build_structured_summary(chapter_text, paragraphs, title, chapter)

    dominant = entity_counts.most_common(1)[0][0] if entity_counts else ""

    # Discover new entity candidates not in the known list
    new_entities = _find_new_entity_candidates(chapter_text, key_entities)

    result = {
        "meta": {"schema_version": "codex-writer/extraction-result/v1"},
        "chapter": chapter,
        "covered_nodes": covered_nodes,
        "missed_nodes": missed_nodes,
        "pending_disambiguation": [],
        "state_deltas": [],
        "entity_deltas": entity_deltas,
        "entities_appeared": entities_appeared,
        "new_entities": new_entities,
        "accepted_events": accepted_events,
        "scenes": scenes,
        "summary_text": summary,
        "dominant_thread": dominant,
    }

    output_path = extraction_result_path(project_root, chapter)
    write_json_atomic(output_path, result)

    return result
