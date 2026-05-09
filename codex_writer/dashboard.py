from pathlib import Path

from codex_writer.core.io import read_json
from codex_writer.core.paths import state_path, memory_path


def build_dashboard(project_root: Path) -> dict:
    cw = project_root / ".codex-writer"
    result = {"project": {}, "chapters": [], "review": {}, "memory": {}, "reading_power": {}, "entities": []}

    sp = state_path(project_root)
    if sp.exists():
        state = read_json(sp)
        result["project"] = {
            "title": _safe_get(project_root, "project.json", "title"),
            "genre": _safe_get(project_root, "project.json", "genre"),
            "total_word_count": state.get("total_word_count", 0),
            "current_chapter": state.get("current_chapter", 0),
            "current_volume": state.get("current_volume", 1),
            "story_status": state.get("story_status", "unknown"),
            "rag_mode": _safe_rag(project_root)
        }
        for ch_key, ch_val in state.get("chapters", {}).items():
            result["chapters"].append({
                "chapter": ch_val.get("chapter", 0),
                "title": ch_val.get("title", ""),
                "status": ch_val.get("status", "unknown"),
                "word_count": ch_val.get("word_count", 0)
            })

    result["chapters"].sort(key=lambda x: x["chapter"])

    reviews_dir = cw / "reviews"
    review_summary = {"total_reviews": 0, "total_blocking": 0, "by_severity": {}}
    if reviews_dir.exists():
        for rp in sorted(reviews_dir.glob("*.json")):
            try:
                rdata = read_json(rp)
                review_summary["total_reviews"] += 1
                review_summary["total_blocking"] += rdata.get("blocking_count", 0)
                for issue in rdata.get("issues", []):
                    sev = issue.get("severity", "unknown")
                    review_summary["by_severity"][sev] = review_summary["by_severity"].get(sev, 0) + 1
            except (ImportError, OSError, ValueError, KeyError):
                pass
    result["review"] = review_summary

    try:
        from codex_writer.memory.scratchpad import get_memory_stats
        result["memory"] = get_memory_stats(project_root)
    except (ImportError, OSError, ValueError, KeyError):
        result["memory"] = {"error": "memory scratchpad unavailable"}

    try:
        from codex_writer.reading_power.tracker import get_debt_summary
        result["reading_power"] = get_debt_summary(project_root)
    except (ImportError, OSError, ValueError, KeyError):
        result["reading_power"] = {"error": "reading power unavailable"}

    try:
        from codex_writer.storage.db import connect_db
        db = cw / "index.sqlite"
        if db.exists():
            with connect_db(project_root) as conn:
                rows = conn.execute("SELECT name, type, current_json FROM entities ORDER BY name").fetchall()
                for row in rows:
                    result["entities"].append({"name": row[0], "type": row[1], "data": row[2][:100] if row[2] else ""})
    except (ImportError, OSError):
        pass

    return result


def format_dashboard_text(data: dict) -> str:
    lines = []
    p = data.get("project", {})
    lines.append("╔══════════════════════════════════════════╗")
    lines.append(f"║  {p.get('title', '未命名')}  ·  {p.get('genre', '')}  ·  {p.get('total_word_count', 0)} 字")
    lines.append(f"║  第 {p.get('current_volume', 1)} 卷  ·  第 {p.get('current_chapter', 0)} 章  ·  RAG: {p.get('rag_mode', 'bm25')}  ·  状态: {p.get('story_status', '-')}")
    lines.append("╠══════════════════════════════════════════╣")

    lines.append("║  章节网格:")
    for ch in data.get("chapters", [])[-10:]:
        status_mark = "[OK]" if ch["status"] == "accepted" else "[NO]" if ch["status"] == "rejected" else "[--]"
        lines.append(f"║  {status_mark} 第{ch['chapter']:04d}章 {ch['title'][:12]}  {ch['word_count']}字  {ch['status']}")
    lines.append("╠══════════════════════════════════════════╣")

    r = data.get("review", {})
    sev_str = ", ".join(f"{k}:{v}" for k, v in r.get("by_severity", {}).items())
    lines.append(f"║  审查: {r.get('total_reviews', 0)}次 | 阻断 {r.get('total_blocking', 0)} | {sev_str}")
    lines.append("╠══════════════════════════════════════════╣")

    m = data.get("memory", {})
    lines.append(f"║  记忆: 活跃 {m.get('episodic_active', 0)} | 归档 {m.get('episodic_archived', 0)} | 长期 {m.get('semantic_total', 0)} | 冲突 {m.get('conflicts_total', 0)}")
    lines.append("╠══════════════════════════════════════════╣")

    rp = data.get("reading_power", {})
    lines.append(f"║  追读力: 开放 {rp.get('open', 0)} | 兑现 {rp.get('paid', 0)} | 过期 {rp.get('expired', 0)} | 最老未兑 Ch.{rp.get('oldest_open', 0)}")
    lines.append("╠══════════════════════════════════════════╣")

    entities = data.get("entities", [])
    if entities:
        ent_str = ", ".join(f"{e['name']}({e['type']})" for e in entities[:8])
        lines.append(f"║  实体: {ent_str}")
    lines.append("╚══════════════════════════════════════════╝")
    return "\n".join(lines)


def _safe_get(root: Path, rel_path: str, key: str) -> str:
    path = root / ".codex-writer" / rel_path
    if path.exists():
        try:
            d = read_json(path)
            return d.get(key, "")
        except (ImportError, OSError, ValueError, KeyError):
            pass
    return ""


def _safe_rag(root: Path) -> str:
    try:
        from codex_writer.runtime.rag import get_search_mode
        return get_search_mode(root)
    except (ImportError, OSError, ValueError, KeyError):
        return "unavailable"
