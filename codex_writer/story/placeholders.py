import re
from pathlib import Path


PLACEHOLDER_PATTERNS = [
    re.compile(r"\[待补充\]"),
    re.compile(r"\[TODO\]", re.IGNORECASE),
    re.compile(r"\[占位\]"),
    re.compile(r"待定"),
    re.compile(r"XXX+"),
]


def find_placeholders(text: str) -> list[dict]:
    results = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for pattern in PLACEHOLDER_PATTERNS:
            for match in pattern.finditer(line):
                results.append({
                    "line": line_no,
                    "pattern": pattern.pattern,
                    "text": match.group(),
                    "context": line.strip()[:80]
                })
    return results


def scan_file_for_placeholders(path: Path) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return find_placeholders(text)


def scan_chapter_placeholders(project_root: Path, chapter: int) -> list[dict]:
    results = []
    from codex_writer.core.paths import chapter_brief_path, review_result_path, extraction_result_path
    files_to_check = [
        ("chapter_brief", chapter_brief_path(project_root, chapter)),
        ("review_result", review_result_path(project_root, chapter)),
        ("extraction_result", extraction_result_path(project_root, chapter)),
    ]
    from codex_writer.core.paths import story_contract_path
    files_to_check.append(("story_contract", story_contract_path(project_root)))
    for label, fpath in files_to_check:
        for finding in scan_file_for_placeholders(fpath):
            finding["file"] = label
            results.append(finding)
    return results


def scan_user_files_placeholders(project_root: Path) -> list[dict]:
    results = []
    for dir_name in ["设定", "大纲", "正文"]:
        user_dir = project_root / dir_name
        if user_dir.exists():
            for fpath in user_dir.rglob("*.md"):
                for finding in scan_file_for_placeholders(fpath):
                    finding["file"] = str(fpath.relative_to(project_root))
                    results.append(finding)
    return results
