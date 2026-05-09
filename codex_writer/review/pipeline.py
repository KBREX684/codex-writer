import re
from pathlib import Path

from codex_writer.core.io import read_json, write_json_atomic, write_markdown_atomic
from codex_writer.core.paths import chapter_brief_path, review_result_path

PACING_LONG_PARAGRAPH = 300
PACING_MIN_DIALOGUE_RATIO = 0.15
COOL_POINT_MIN_TEXT_LEN = 20

AI_FLAVOR_PATTERNS = [
    "命运的齿轮",
    "然而，",
    "值得注意的是",
    "总的来说",
    "在某种程度上",
    "深吸一口气",
    "不禁",
    "众所周知",
    "毋庸置疑",
]

COOL_POINT_PATTERNS = [
    r"(?:获得|得到|突破|晋升|踏入|升入|晋级|提升.{0,5}境界)",
    r"(?:震惊|难以置信|目瞪口呆|不敢置信|倒吸一口凉气)",
    r"(?:身份|实力|秘密|真相).{0,10}(?:揭露|暴露|揭开|公布)",
    r"(?:反转|逆转|突变|颠覆)",
    r"(?:击败|碾压|秒杀|轻易.{0,5}战胜)",
]


def _check_cool_points(text: str) -> list[dict]:
    issues = []
    matches = []
    for pattern in COOL_POINT_PATTERNS:
        for match in re.finditer(pattern, text):
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            matches.append({
                "position": match.start(),
                "text": match.group(),
                "context": text[start:end]
            })

    word_count = len(text)
    if word_count > 0 and len(matches) == 0:
        issues.append({
            "severity": "medium",
            "category": "logic",
            "location": "全文",
            "description": "未检测到爽点模式（兑现/反转/打脸/震惊），建议增加至少一处小型爽点",
            "evidence": "",
            "fix_hint": "在章节中插入一处兑现、反转、打脸或震惊事件",
            "blocking": False,
            "chapter": 0
        })

    return issues


def _check_pacing(text: str) -> list[dict]:
    issues = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    slow_paragraphs = 0
    for i, para in enumerate(paragraphs):
        if len(para) > PACING_LONG_PARAGRAPH:
            slow_paragraphs += 1
            if slow_paragraphs >= 3:
                issues.append({
                    "severity": "low",
                    "category": "logic",
                    "location": f"第{i + 1}段附近",
                    "description": f"连续 {slow_paragraphs} 段超过 {PACING_LONG_PARAGRAPH} 字，节奏偏慢",
                    "evidence": para[:80],
                    "fix_hint": "拆分长段落或插入对话/场景切换",
                    "blocking": False,
                    "chapter": 0
                })
                break
        else:
            slow_paragraphs = 0

    dialogue_marks = ("\u201c", "\u2018", "\u300c", "\u300d", "\u300e", "\u300f")
    dialogue_lines = sum(1 for line in text.splitlines() if line.strip() and line.strip()[0] in dialogue_marks)
    total_lines = max(len([l for l in text.splitlines() if l.strip()]), 1)
    dialogue_ratio = dialogue_lines / total_lines

    if dialogue_ratio < PACING_MIN_DIALOGUE_RATIO:
        issues.append({
            "severity": "low",
            "category": "logic",
            "location": "全文",
            "description": f"对话占比仅 {dialogue_ratio:.0%}，叙述过重可能降低可读性",
            "evidence": f"对话行数: {dialogue_lines}/{total_lines}",
            "fix_hint": "增加角色互动或内心独白，提高对话密度",
            "blocking": False,
            "chapter": 0
        })

    return issues


def _check_continuity(project_root: Path, chapter: int, text: str) -> list[dict]:
    issues = []
    prev_chapter = chapter - 1
    if prev_chapter < 1:
        return issues

    from codex_writer.core.paths import summary_path
    prev_summary = summary_path(project_root, prev_chapter)
    if not prev_summary.exists():
        issues.append({
            "severity": "low",
            "category": "continuity",
            "location": f"第{prev_chapter}章→第{chapter}章",
            "description": f"未找到第{prev_chapter}章摘要，无法检查连续性",
            "evidence": "",
            "fix_hint": "确保前一章已通过 commit 生成摘要",
            "blocking": False,
            "chapter": 0
        })
        return issues

    prev_text = prev_summary.read_text(encoding="utf-8", errors="replace")
    if len(text) < COOL_POINT_MIN_TEXT_LEN and prev_text:
        issues.append({
            "severity": "high",
            "category": "continuity",
            "location": f"第{prev_chapter}章→第{chapter}章",
            "description": "当前章正文过短，可能出现连续性断裂",
            "evidence": "",
            "fix_hint": "确保本章与上一章有明确的情节承接",
            "blocking": False,
            "chapter": 0
        })

    return issues


def _check_setting_consistency(project_root: Path, text: str, chapter: int) -> list[dict]:
    issues = []
    from codex_writer.core.paths import references_dir_path
    ref_dir = references_dir_path(project_root)
    world_rules_path = ref_dir / "shared" / "core-constraints.md"
    if not world_rules_path.exists():
        return issues

    rules_text = world_rules_path.read_text(encoding="utf-8", errors="replace")
    contradictions = []
    for line in rules_text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        for keyword in ["推翻", "改变", "打破", "取消"]:
            if keyword in line and keyword in text:
                contradictions.append(line[:80])

    if contradictions:
        issues.append({
            "severity": "medium",
            "category": "setting",
            "location": "全文",
            "description": f"正文可能涉及世界规则变化: {contradictions[0]}",
            "evidence": contradictions[0],
            "fix_hint": "确认是否违反已设定的世界规则，或是有意的新规则揭示",
            "blocking": False,
            "chapter": 0
        })

    return issues


def _check_character_consistency(project_root: Path, text: str, chapter: int) -> list[dict]:
    issues = []
    from codex_writer.core.paths import references_dir_path
    ref_dir = references_dir_path(project_root)
    char_csv = ref_dir / "csv" / "人设与关系.csv"
    if not char_csv.exists():
        return issues

    import csv
    try:
        content = char_csv.read_text(encoding="utf-8", errors="replace")
        reader = csv.DictReader(content.splitlines())
        for row in reader:
            char_name = row.get("tag", "")
            char_rule = row.get("content", "")
            if char_name and char_name in text:
                opposing_keywords = []
                if "弱点" in char_rule:
                    opposing_keywords = ["完美", "全能", "无敌", "毫无破绽"]
                if "动机" in char_rule:
                    opposing_keywords = ["随意", "漫无目的", "毫无理由"]
                for kw in opposing_keywords:
                    if kw in text:
                        issues.append({
                            "severity": "low",
                            "category": "character",
                            "location": f"角色: {char_name}",
                            "description": f"角色「{char_name}」行为可能与设定冲突 ({kw})",
                            "evidence": char_rule[:80],
                            "fix_hint": f"检查{char_name}的行为是否符合设定: {char_rule[:60]}",
                            "blocking": False,
                            "chapter": 0
                        })
                        break
    except (ImportError, OSError):
        pass

    return issues


def review_chapter(project_root: Path, chapter: int, chapter_text: str) -> dict:
    issues = []

    if not chapter_text.strip():
        issues.append({
            "severity": "critical",
            "category": "logic",
            "location": "全文",
            "description": "正文为空",
            "evidence": "",
            "fix_hint": "补写正文后重新审查",
            "blocking": True,
            "chapter": chapter
        })

    brief_path = chapter_brief_path(project_root, chapter)
    if not brief_path.exists():
        issues.append({
            "severity": "high",
            "category": "continuity",
            "location": "章节任务书",
            "description": "章节任务书缺失",
            "evidence": "",
            "fix_hint": "先运行 plan 创建任务书",
            "blocking": True,
            "chapter": chapter
        })

    for pattern in AI_FLAVOR_PATTERNS:
        if pattern in chapter_text:
            issues.append({
                "severity": "low",
                "category": "ai_flavor",
                "location": f"发现模式: {pattern}",
                "description": f"正文包含AI模板句式「{pattern}」",
                "evidence": pattern,
                "fix_hint": "改写该句，使用更自然的表达",
                "blocking": False,
                "chapter": chapter
            })

    issues.extend(_check_cool_points(chapter_text))
    for i in issues:
        if i.get("chapter") == 0:
            i["chapter"] = chapter

    issues.extend(_check_pacing(chapter_text))
    for i in issues:
        if i.get("chapter") == 0:
            i["chapter"] = chapter

    issues.extend(_check_continuity(project_root, chapter, chapter_text))
    for i in issues:
        if i.get("chapter") == 0:
            i["chapter"] = chapter

    issues.extend(_check_setting_consistency(project_root, chapter_text, chapter))
    for i in issues:
        if i.get("chapter") == 0:
            i["chapter"] = chapter

    issues.extend(_check_character_consistency(project_root, chapter_text, chapter))
    for i in issues:
        if i.get("chapter") == 0:
            i["chapter"] = chapter

    try:
        from codex_writer.reading_power.tracker import get_debt_summary, detect_hooks_from_text
        rp_hooks = detect_hooks_from_text(chapter_text, chapter)
        rp_summary = get_debt_summary(project_root)
        if rp_summary["open"] > 3:
            issues.append({
                "severity": "medium",
                "category": "logic",
                "location": "全文",
                "description": f"当前有 {rp_summary['open']} 个未兑现的读者期待，最老的来自第 {rp_summary['oldest_open']} 章",
                "evidence": "",
                "fix_hint": "在近期章节中兑现部分期待，或标记为过期",
                "blocking": False,
                "chapter": chapter
            })
    except (ImportError, OSError):
        pass

    blocking_count = sum(1 for i in issues if i.get("blocking", False))

    result = {
        "meta": {"schema_version": "codex-writer/review-result/v1"},
        "chapter": chapter,
        "issues": issues,
        "summary": f"共发现 {len(issues)} 个问题，其中 {blocking_count} 个阻断",
        "blocking_count": blocking_count
    }

    review_path = review_result_path(project_root, chapter)
    write_json_atomic(review_path, result)

    _write_review_markdown(project_root, chapter, result)

    return result


def _write_review_markdown(project_root: Path, chapter: int, result: dict) -> None:
    md_path = project_root / ".codex-writer" / "reviews" / f"第{chapter:04d}章审查报告.md"
    lines = [f"# 第{chapter:04d}章 审查报告", ""]
    lines.append(f"阻断问题: {result['blocking_count']} | 总问题: {len(result['issues'])}")
    lines.append("")

    by_severity = {"critical": [], "high": [], "medium": [], "low": []}
    for issue in result["issues"]:
        by_severity.setdefault(issue["severity"], []).append(issue)

    for sev, items in by_severity.items():
        if not items:
            continue
        sev_label = {"critical": "🔴 严重", "high": "🟠 高", "medium": "🟡 中", "low": "🔵 低"}
        lines.append(f"## {sev_label.get(sev, sev)} ({len(items)} 项)")
        lines.append("")
        for issue in items:
            lines.append(f"- **{issue['category']}** | {issue['location']}")
            lines.append(f"  {issue['description']}")
            if issue["evidence"]:
                lines.append(f"  > {issue['evidence']}")
            if issue["fix_hint"]:
                lines.append(f"  → {issue['fix_hint']}")
            lines.append("")

    write_markdown_atomic(md_path, "\n".join(lines))


def run_review(project_root: Path, chapter: int) -> dict:
    from codex_writer.core.paths import chapter_md_path
    brief = chapter_brief_path(project_root, chapter)
    title = ""
    if brief.exists():
        data = read_json(brief)
        title = data.get("title", "")
    md_path = chapter_md_path(project_root, chapter, title)
    text = ""
    if md_path.exists():
        text = md_path.read_text(encoding="utf-8")
    return review_chapter(project_root, chapter, text)
