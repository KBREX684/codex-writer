from pathlib import Path

from codex_writer.core.io import read_json, write_json_atomic
from codex_writer.core.paths import chapter_brief_path, review_result_path


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

    return result


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
