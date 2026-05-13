import re
from pathlib import Path

from codex_writer.core.io import read_json, write_json_atomic, write_markdown_atomic
from codex_writer.core.paths import chapter_brief_path, review_result_path

PACING_LONG_PARAGRAPH = 300
PACING_MIN_DIALOGUE_RATIO = 0.15
COOL_POINT_MIN_TEXT_LEN = 20

# Context window (chars) around an AI-flavor match used to report evidence.
_AI_FLAVOR_CONTEXT = 40

# ── AI 腔模式：(字符串精确匹配, 说明) ─────────────────────────────────────────
# 每一项是 (pattern, description, context_required)
# context_required=True 表示仅当该词独立成句或在非引号环境中才报告
_AI_FLAVOR_ENTRIES: list[tuple[str, str, bool]] = [
    # 经典 AI 句式
    ("命运的齿轮", "AI 模板：「命运的齿轮」", False),
    ("值得注意的是", "AI 模板：「值得注意的是」", False),
    ("总的来说", "AI 模板：「总的来说」", False),
    ("在某种程度上", "AI 模板：「在某种程度上」", False),
    ("众所周知", "AI 模板：「众所周知」", False),
    ("毋庸置疑", "AI 模板：「毋庸置疑」", False),
    ("深吸一口气", "AI 模板：「深吸一口气」（滥用过渡词）", False),
    ("这时他意识到", "AI 模板：视角切换套话", False),
    ("这时她意识到", "AI 模板：视角切换套话", False),
    ("思绪万千", "AI 模板：情绪堆叠套话", False),
    ("内心五味杂陈", "AI 模板：情绪堆叠套话", False),
    ("令人窒息", "AI 模板：形容词堆叠", False),
    ("不由得", "AI 模板：「不由得」（可改为直接动作）", False),
    ("浮现在脑海", "AI 模板：「浮现在脑海」（可改为具体感官）", False),
    ("心中一震", "AI 模板：「心中一震」（过度使用）", False),
    ("不禁感叹", "AI 模板：「不禁感叹」", False),
    ("此刻的他", "AI 模板：「此刻的他/她」（距离感叙述）", False),
    ("此刻的她", "AI 模板：「此刻的她」", False),
    ("下一章将会", "AI 元叙述：直接打破第四堵墙", False),
    ("且听下回分解", "AI 元叙述：评书套语，现代网文不适用", False),
    ("随着剧情的发展", "AI 元叙述：作者视角侵入", False),
    ("读者们", "AI 元叙述：直接称呼读者", False),
    # 「不禁」单独检查（上下文相关）
    ("不禁", "AI 模板：「不禁」（频繁使用时显 AI 腔）", True),
    # 「然而，」单独成段首才报告（上下文相关）
    ("然而，", "AI 衔接：「然而，」独立段首（过度转折）", True),
]

# 上下文相关 AI 腔：仅当出现在段落开头时才报告
_PARAGRAPH_HEAD_PATTERNS = {"然而，"}
# 全局出现超过此次数才报告（避免单次误伤）
_AI_FLAVOR_REPEAT_THRESHOLD = {"不禁": 2}

COOL_POINT_PATTERNS = [
    r"(?:突破|晋升|踏入|升入|晋级|提升.{0,5}境界|境界.{0,5}突破)",
    r"(?:震惊|难以置信|目瞪口呆|不敢置信|倒吸一口凉气)",
    r"(?:身份|实力|秘密|真相).{0,10}(?:揭露|暴露|揭开|公布)",
    r"(?:反转|逆转|颠覆).{0,15}(?:局面|预期|结果|命运|形势)",
    r"(?:一击|一掌|一剑|一拳).{0,10}(?:击败|击倒|震退|碾压|秒杀)",
    r"(?:打脸|狠狠.{0,5}回击|以牙还牙)",
    r"(?:身份曝光|真实身份|隐藏实力)",
]

# 章末钩子检测：最后两段落至少有一段命中则认为有章末钩
_CHAPTER_END_HOOK_PATTERNS = [
    r"[？?！!…]{1,}",
    r"(?:却不知|殊不知|谁也没想到)",
    r"(?:忽然|突然|陡然).{0,20}(?:响起|出现|袭来|传来)",
    r"(?:来不及|已经太迟|为时已晚)",
    r"(?:危险|威胁|杀机).{0,10}(?:逼近|降临|显现)",
]


def _find_in_text_with_context(text: str, pattern: str, context_chars: int = _AI_FLAVOR_CONTEXT) -> list[str]:
    """Return context snippets for all occurrences of *pattern* in *text*."""
    results = []
    start = 0
    while True:
        idx = text.find(pattern, start)
        if idx == -1:
            break
        ctx_start = max(0, idx - context_chars)
        ctx_end = min(len(text), idx + len(pattern) + context_chars)
        results.append(text[ctx_start:ctx_end])
        start = idx + 1
    return results


def _check_ai_flavor(text: str, chapter: int) -> list[dict]:
    """Detect AI-flavor patterns with context-window matching."""
    issues = []
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]

    for pattern, description, context_required in _AI_FLAVOR_ENTRIES:
        occurrences = _find_in_text_with_context(text, pattern)
        if not occurrences:
            continue

        # Context-required patterns: apply extra filters
        if context_required and pattern in _PARAGRAPH_HEAD_PATTERNS:
            head_count = sum(1 for para in paragraphs if para.startswith(pattern))
            if head_count < 2:
                continue

        if context_required and pattern in _AI_FLAVOR_REPEAT_THRESHOLD:
            if len(occurrences) < _AI_FLAVOR_REPEAT_THRESHOLD[pattern]:
                continue

        issues.append({
            "severity": "low",
            "category": "ai_flavor",
            "location": f"发现模式: {pattern}（共 {len(occurrences)} 处）",
            "description": description,
            "evidence": pattern,
            "fix_hint": f"改写该句式，使用更自然、更具体的表达。示例片段：「{occurrences[0][:60]}」",
            "blocking": False,
            "chapter": chapter,
        })

    return issues


def _check_cool_points(text: str, chapter: int) -> list[dict]:
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

    if len(text) > COOL_POINT_MIN_TEXT_LEN and not matches:
        issues.append({
            "severity": "medium",
            "category": "logic",
            "location": "全文",
            "description": "未检测到爽点模式（兑现/反转/打脸/震惊），建议增加至少一处小型爽点",
            "evidence": "",
            "fix_hint": "在章节中插入一处兑现、反转、打脸或震惊事件",
            "blocking": False,
            "chapter": chapter,
        })

    return issues


def _check_chapter_end_hook(text: str, chapter: int) -> list[dict]:
    """Warn if the chapter ending doesn't contain a suspense hook."""
    if not text.strip():
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    tail = "\n".join(paragraphs[-2:]) if len(paragraphs) >= 2 else paragraphs[-1] if paragraphs else ""
    for pattern in _CHAPTER_END_HOOK_PATTERNS:
        if re.search(pattern, tail):
            return []
    return [{
        "severity": "medium",
        "category": "logic",
        "location": "章节结尾",
        "description": "章末未检测到有效悬念钩子（疑问/意外/新威胁），可能影响追读率",
        "evidence": tail[:80] if tail else "",
        "fix_hint": "在最后一到两段加入未解疑问、突发事件或新的危机",
        "blocking": False,
        "chapter": chapter,
    }]


def _check_pacing(text: str, chapter: int) -> list[dict]:
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
                    "chapter": chapter,
                })
                break
        else:
            slow_paragraphs = 0

    dialogue_marks = ("\u201c", "\u2018", "\u300c", "\u300d", "\u300e", "\u300f")
    dialogue_lines = sum(1 for line in text.splitlines() if line.strip() and line.strip()[0] in dialogue_marks)
    total_lines = max(len([ln for ln in text.splitlines() if ln.strip()]), 1)
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
            "chapter": chapter,
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
            "chapter": chapter,
        })
        return issues

    if len(text) < COOL_POINT_MIN_TEXT_LEN:
        issues.append({
            "severity": "high",
            "category": "continuity",
            "location": f"第{prev_chapter}章→第{chapter}章",
            "description": "当前章正文过短，可能出现连续性断裂",
            "evidence": "",
            "fix_hint": "确保本章与上一章有明确的情节承接",
            "blocking": False,
            "chapter": chapter,
        })

    return issues


def _check_setting_consistency(project_root: Path, text: str, chapter: int) -> list[dict]:
    """Check whether the chapter text contradicts named hard rules.

    Instead of keyword co-occurrence, we now look for sentences in the text
    that contain a constraint keyword AND contain one of the explicit
    ``"禁止/不允许/绝对不"`` negation markers which would indicate the rule
    is being discussed as if it were being broken.
    """
    issues = []
    from codex_writer.core.paths import references_dir_path
    ref_dir = references_dir_path(project_root)
    world_rules_path = ref_dir / "shared" / "core-constraints.md"
    if not world_rules_path.exists():
        return issues

    rules_text = world_rules_path.read_text(encoding="utf-8", errors="replace")
    # Extract rule lines (non-comment, non-empty)
    rule_lines = [
        line.strip() for line in rules_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not rule_lines:
        return issues

    # Build per-rule keyword sets (2-char n-gram tokens from rule line).
    # For each sentence in the chapter that shares ≥2 keywords with a rule
    # AND contains a negation/violation marker, report a potential conflict.
    violation_markers = ["违反", "打破", "无视", "推翻", "取消", "改变了", "不再", "已不"]
    sentences = re.split(r"[。！？\n]", text)

    for rule_line in rule_lines[:30]:  # cap rule iterations to avoid excessive per-sentence checks
        rule_keywords = set(rule_line[i:i + 2] for i in range(len(rule_line) - 1))
        if len(rule_keywords) < 2:
            continue
        for sent in sentences:
            if len(sent) < 5:
                continue
            sent_keywords = set(sent[i:i + 2] for i in range(len(sent) - 1))
            overlap = rule_keywords & sent_keywords
            has_violation = any(marker in sent for marker in violation_markers)
            if len(overlap) >= 3 and has_violation:
                issues.append({
                    "severity": "medium",
                    "category": "setting",
                    "location": "全文",
                    "description": f"正文可能违反世界规则「{rule_line[:60]}」",
                    "evidence": sent[:80],
                    "fix_hint": "确认是否有意改写规则；如非有意，请恢复设定一致性",
                    "blocking": False,
                    "chapter": chapter,
                })
                break  # one report per rule is enough

    return issues


def _check_character_consistency(project_root: Path, text: str, chapter: int) -> list[dict]:
    """Check character behaviour against character card definitions.

    Only report a conflict when the character appears AND the chapter
    contains a sentence that simultaneously mentions the character name
    AND a keyword that clearly contradicts that character's defined
    weakness/motivation in the same sentence (±100 chars window).
    """
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
            char_name = row.get("tag", "").strip()
            char_rule = row.get("content", "").strip()
            if not char_name or char_name not in text:
                continue

            opposing_keywords = []
            if "弱点" in char_rule:
                opposing_keywords = ["完美无缺", "天下无敌", "毫无破绽", "从未失败"]
            if "动机" in char_rule:
                opposing_keywords = ["毫无目的", "漫无目的", "毫无理由地"]
            if not opposing_keywords:
                continue

            # Check within a local window around each character name occurrence.
            # Pre-compile the pattern once to avoid redundant compilation per iteration.
            conflict_found = False
            char_pattern = re.compile(re.escape(char_name))
            for match in char_pattern.finditer(text):
                window_start = max(0, match.start() - 100)
                window_end = min(len(text), match.end() + 100)
                window = text[window_start:window_end]
                for kw in opposing_keywords:
                    if kw in window:
                        issues.append({
                            "severity": "low",
                            "category": "character",
                            "location": f"角色: {char_name}",
                            "description": f"角色「{char_name}」附近出现「{kw}」，可能与设定冲突",
                            "evidence": window[:80],
                            "fix_hint": f"检查{char_name}的行为是否符合设定: {char_rule[:60]}",
                            "blocking": False,
                            "chapter": chapter,
                        })
                        conflict_found = True
                        break  # one report per character per run
                if conflict_found:
                    break

    except (ImportError, OSError):
        pass

    return issues


def _check_word_count(project_root: Path, text: str, chapter: int) -> list[dict]:
    """Block if actual word count deviates severely from target_words in the brief."""
    issues = []
    try:
        brief = read_json(chapter_brief_path(project_root, chapter))
        target = int(brief.get("target_words") or 0)
    except (OSError, ValueError, TypeError):
        return issues
    if target <= 0:
        return issues

    # Count Chinese characters + common Chinese punctuation (exclude whitespace &
    # Markdown structural characters such as #, *, >, ─, etc.).
    actual = sum(
        1 for ch in text
        if "\u4e00" <= ch <= "\u9fff"
        or "\u3000" <= ch <= "\u303f"  # CJK symbols & punctuation
        or "\uff00" <= ch <= "\uffef"  # fullwidth forms
    )
    if actual == 0:
        return issues

    ratio = actual / target
    if ratio < 0.5:
        issues.append({
            "severity": "high",
            "category": "word_count",
            "location": "全文",
            "description": (
                f"实际字数 {actual} 距目标 {target} 偏差 {1 - ratio:.0%}，"
                "疑似模型截断或提前收尾（blocking）"
            ),
            "evidence": f"actual={actual} target={target}",
            "fix_hint": "检查 max_tokens 设置，或要求模型补写剩余内容",
            "blocking": True,
            "chapter": chapter,
        })
    elif ratio < 0.7:
        issues.append({
            "severity": "medium",
            "category": "word_count",
            "location": "全文",
            "description": f"实际字数 {actual} 距目标 {target} 偏差 {1 - ratio:.0%}，章节偏短",
            "evidence": f"actual={actual} target={target}",
            "fix_hint": "适当扩写场景细节或对话",
            "blocking": False,
            "chapter": chapter,
        })
    return issues


def _check_entity_state_consistency(project_root: Path, text: str, chapter: int) -> list[dict]:
    """Warn if an entity that is recorded as dead/removed appears in the chapter text.

    Reads the ``state_changes`` table from index.sqlite.  Only reports when
    the entity name actually appears verbatim in the prose.
    """
    issues = []
    try:
        from codex_writer.storage.db import connect_db
        with connect_db(project_root) as conn:
            rows = conn.execute(
                """
                SELECT entity_id, field, new_value, chapter AS changed_chapter
                FROM state_changes
                WHERE field IN ('status', 'alive', 'state')
                  AND new_value IN ('dead', 'deceased', '死亡', '消失', 'removed', '被消灭')
                  AND chapter < ?
                """,
                (chapter,),
            ).fetchall()
    except Exception:
        return issues

    for row in rows:
        entity_id = row["entity_id"]
        changed_ch = row["changed_chapter"]
        if entity_id in text:
            issues.append({
                "severity": "high",
                "category": "continuity",
                "location": f"角色/实体: {entity_id}",
                "description": (
                    f"实体「{entity_id}」在第{changed_ch}章已标记为「{row['new_value']}」，"
                    f"但在第{chapter}章正文中仍出现"
                ),
                "evidence": "",
                "fix_hint": f"确认第{chapter}章对「{entity_id}」的处理是否符合第{changed_ch}章设定",
                "blocking": False,
                "chapter": chapter,
            })
    return issues


# Minimum number of preceding chapters to check for cool-point cadence.
_COOL_POINT_CADENCE_WINDOW = 5


def _check_cool_point_cadence(project_root: Path, chapter: int) -> list[dict]:
    """Warn if no cool point has been detected in the last N chapters.

    Reads review results from disk to check whether recent chapters had cool
    points.  Only fires when there are enough committed review results.
    """
    issues = []
    from codex_writer.core.paths import review_result_path as rrp
    no_cool = 0
    checked = 0
    for offset in range(1, _COOL_POINT_CADENCE_WINDOW + 1):
        prev = chapter - offset
        if prev < 1:
            break
        rp = rrp(project_root, prev)
        if not rp.exists():
            continue
        try:
            data = read_json(rp)
            prev_issues = data.get("issues", [])
            # A chapter had no cool point if the review emitted an "未检测到爽点" issue.
            had_no_cool_issue = any(
                "未检测到爽点" in i.get("description", "") for i in prev_issues
            )
            if had_no_cool_issue:
                no_cool += 1
            checked += 1
        except (OSError, ValueError, TypeError):
            pass

    if checked >= 3 and no_cool >= checked:
        issues.append({
            "severity": "medium",
            "category": "pacing",
            "location": "近期章节",
            "description": (
                f"最近 {checked} 章均未检测到爽点（兑现/反转/打脸/震惊），"
                "可能导致读者流失，建议本章或下章安排一个中型兑现"
            ),
            "evidence": f"连续 {no_cool} 章无爽点",
            "fix_hint": "在本章中加入至少一处兑现、反转、打脸或震惊事件",
            "blocking": False,
            "chapter": chapter,
        })
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

    issues.extend(_check_ai_flavor(chapter_text, chapter))
    issues.extend(_check_word_count(project_root, chapter_text, chapter))
    issues.extend(_check_cool_points(chapter_text, chapter))
    issues.extend(_check_chapter_end_hook(chapter_text, chapter))
    issues.extend(_check_pacing(chapter_text, chapter))
    issues.extend(_check_continuity(project_root, chapter, chapter_text))
    issues.extend(_check_setting_consistency(project_root, chapter_text, chapter))
    issues.extend(_check_character_consistency(project_root, chapter_text, chapter))
    issues.extend(_check_entity_state_consistency(project_root, chapter_text, chapter))
    issues.extend(_check_cool_point_cadence(project_root, chapter))

    try:
        from codex_writer.reading_power.tracker import get_debt_summary, detect_hooks_from_text
        detect_hooks_from_text(chapter_text, chapter)
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
