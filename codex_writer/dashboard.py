from __future__ import annotations

from html import escape
from pathlib import Path

from codex_writer.core.io import read_json, write_markdown_atomic
from codex_writer.core.paths import resolve_in_project, state_path


def build_dashboard(project_root: Path) -> dict:
    cw = project_root / ".codex-writer"
    result = {
        "project": {},
        "chapters": [],
        "review": {},
        "memory": {},
        "reading_power": {},
        "entities": [],
    }

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
            "rag_mode": _safe_rag(project_root),
        }
        for ch_val in state.get("chapters", {}).values():
            result["chapters"].append({
                "chapter": ch_val.get("chapter", 0),
                "title": ch_val.get("title", ""),
                "status": ch_val.get("status", "unknown"),
                "word_count": ch_val.get("word_count", 0),
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
                    result["entities"].append({
                        "name": row[0],
                        "type": row[1],
                        "data": row[2][:100] if row[2] else "",
                    })
    except (ImportError, OSError):
        pass

    return result


def format_dashboard_text(data: dict) -> str:
    lines = []
    p = data.get("project", {})
    width = 72
    lines.append("+" + "-" * width + "+")
    lines.append(f"| Codex Writer Dashboard".ljust(width + 1) + "|")
    lines.append("+" + "-" * width + "+")
    lines.append(f"书名: {p.get('title', '未命名')} | 类型: {p.get('genre', '-')}")
    lines.append(
        f"进度: 第 {p.get('current_volume', 1)} 卷 / 第 {p.get('current_chapter', 0)} 章 | "
        f"总字数: {p.get('total_word_count', 0)} | RAG: {p.get('rag_mode', 'bm25')}"
    )
    lines.append(f"状态: {p.get('story_status', '-')}")
    lines.append("")
    lines.append("章节网格")
    for ch in data.get("chapters", [])[-10:]:
        status_mark = "[OK]" if ch["status"] == "accepted" else "[NO]" if ch["status"] == "rejected" else "[--]"
        lines.append(f"  {status_mark} 第{ch['chapter']:04d}章 {ch['title'][:18]} | {ch['word_count']}字 | {ch['status']}")
    if not data.get("chapters"):
        lines.append("  暂无章节")

    r = data.get("review", {})
    sev_str = ", ".join(f"{k}:{v}" for k, v in r.get("by_severity", {}).items()) or "无"
    lines.append("")
    lines.append(f"审查: {r.get('total_reviews', 0)} 次 | 阻断 {r.get('total_blocking', 0)} | 严重度: {sev_str}")

    m = data.get("memory", {})
    lines.append(
        "记忆: "
        f"活跃 {m.get('episodic_active', 0)} | "
        f"归档 {m.get('episodic_archived', 0)} | "
        f"长期 {m.get('semantic_total', 0)} | "
        f"冲突 {m.get('conflicts_total', 0)}"
    )

    rp = data.get("reading_power", {})
    lines.append(
        "追读力: "
        f"开放 {rp.get('open', 0)} | "
        f"兑现 {rp.get('paid', 0)} | "
        f"过期 {rp.get('expired', 0)} | "
        f"最老未兑现 Ch.{rp.get('oldest_open', 0)}"
    )

    entities = data.get("entities", [])
    if entities:
        ent_str = ", ".join(f"{e['name']}({e['type']})" for e in entities[:8])
        lines.append(f"实体: {ent_str}")
    else:
        lines.append("实体: 暂无")
    return "\n".join(lines)


def default_dashboard_html_path(project_root: Path) -> Path:
    return resolve_in_project(project_root, ".codex-writer/dashboard/index.html")


def write_dashboard_html(project_root: Path, data: dict, output: str | None = None) -> Path:
    output_path = resolve_in_project(project_root, output) if output else default_dashboard_html_path(project_root)
    write_markdown_atomic(output_path, render_dashboard_html(data))
    return output_path


def render_dashboard_html(data: dict) -> str:
    p = data.get("project", {})
    chapters = data.get("chapters", [])
    review = data.get("review", {})
    memory = data.get("memory", {})
    reading_power = data.get("reading_power", {})
    entities = data.get("entities", [])

    accepted = sum(1 for ch in chapters if ch.get("status") == "accepted")
    rejected = sum(1 for ch in chapters if ch.get("status") == "rejected")
    total_words = int(p.get("total_word_count", 0) or 0)
    current_chapter = int(p.get("current_chapter", 0) or 0)
    progress_label = f"{accepted}/{len(chapters)}" if chapters else "0/0"
    health_label = "可继续写作" if review.get("total_blocking", 0) == 0 else "存在阻断"
    health_class = "good" if review.get("total_blocking", 0) == 0 else "danger"

    chapter_tiles = "\n".join(_chapter_tile(ch) for ch in chapters[-24:]) or '<div class="empty">暂无章节记录</div>'
    entity_rows = "\n".join(_entity_row(e) for e in entities[:10]) or '<div class="empty">暂无实体投影</div>'
    severity_rows = _severity_rows(review.get("by_severity", {}))

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(str(p.get('title') or 'Codex Writer'))} - Dashboard</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b0c0f;
      --panel: #111318;
      --panel-2: #171a21;
      --line: #2a2f3a;
      --muted: #8d96a8;
      --text: #f2f5f8;
      --soft: #c7ceda;
      --green: #7dd3a7;
      --yellow: #f0c66a;
      --red: #ff8b8b;
      --blue: #8ab4ff;
      --ink: #050608;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      letter-spacing: 0;
    }}
    .shell {{
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      min-height: 100vh;
    }}
    .side {{
      border-right: 1px solid var(--line);
      background: #090a0d;
      padding: 28px 22px;
      position: sticky;
      top: 0;
      height: 100vh;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 34px;
    }}
    .mark {{
      width: 34px;
      height: 34px;
      border: 1px solid #596170;
      display: grid;
      place-items: center;
      font-weight: 700;
      color: var(--text);
      background: #111318;
    }}
    .brand h1 {{
      margin: 0;
      font-size: 17px;
      line-height: 1.2;
      font-weight: 650;
    }}
    .brand span {{
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font-size: 12px;
    }}
    .nav {{
      display: grid;
      gap: 8px;
      color: var(--soft);
      font-size: 14px;
    }}
    .nav a {{
      color: inherit;
      text-decoration: none;
      padding: 10px 0;
      border-bottom: 1px solid rgba(255,255,255,0.05);
    }}
    .main {{
      padding: 32px;
      max-width: 1440px;
      width: 100%;
      margin: 0 auto;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-start;
      margin-bottom: 28px;
    }}
    .eyebrow {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 10px;
    }}
    h2 {{
      margin: 0;
      font-size: clamp(28px, 4vw, 52px);
      line-height: 1.02;
      letter-spacing: 0;
      max-width: 920px;
    }}
    .subtitle {{
      margin-top: 14px;
      color: var(--soft);
      font-size: 15px;
      max-width: 820px;
    }}
    .status-pill {{
      border: 1px solid var(--line);
      padding: 12px 14px;
      min-width: 160px;
      text-align: right;
      background: var(--panel);
      color: var(--soft);
    }}
    .status-pill strong {{
      display: block;
      color: var(--text);
      font-size: 16px;
      margin-bottom: 4px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 14px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 18px;
      min-height: 150px;
    }}
    .metric {{
      grid-column: span 3;
    }}
    .wide {{
      grid-column: span 8;
    }}
    .sidepanel {{
      grid-column: span 4;
    }}
    .full {{
      grid-column: 1 / -1;
    }}
    .label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 12px;
    }}
    .number {{
      font-size: 38px;
      line-height: 1;
      font-weight: 680;
      color: var(--text);
    }}
    .number small {{
      color: var(--muted);
      font-size: 14px;
      font-weight: 500;
    }}
    .meta {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
    }}
    .good {{ color: var(--green); }}
    .warn {{ color: var(--yellow); }}
    .danger {{ color: var(--red); }}
    .chapter-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
      gap: 10px;
    }}
    .chapter {{
      border: 1px solid var(--line);
      background: var(--panel-2);
      padding: 12px;
      min-height: 96px;
    }}
    .chapter.accepted {{ border-color: rgba(125, 211, 167, 0.45); }}
    .chapter.rejected {{ border-color: rgba(255, 139, 139, 0.45); }}
    .chapter-num {{
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .chapter-title {{
      font-size: 14px;
      line-height: 1.35;
      min-height: 38px;
      word-break: break-word;
    }}
    .chapter-foot {{
      margin-top: 12px;
      display: flex;
      justify-content: space-between;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }}
    .list {{
      display: grid;
      gap: 10px;
    }}
    .row {{
      display: grid;
      grid-template-columns: minmax(80px, 140px) 1fr;
      gap: 14px;
      padding: 11px 0;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      color: var(--soft);
      font-size: 13px;
    }}
    .row strong {{
      color: var(--text);
      font-weight: 600;
    }}
    .bar {{
      height: 8px;
      background: #232833;
      margin-top: 18px;
      overflow: hidden;
    }}
    .bar span {{
      display: block;
      height: 100%;
      width: {_pct(accepted, max(len(chapters), 1))}%;
      background: var(--green);
    }}
    .empty {{
      color: var(--muted);
      border: 1px dashed var(--line);
      padding: 18px;
      font-size: 14px;
    }}
    .footer {{
      margin-top: 18px;
      color: var(--muted);
      font-size: 12px;
    }}
    @media (max-width: 980px) {{
      .shell {{ grid-template-columns: 1fr; }}
      .side {{
        position: static;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}
      .nav {{ grid-template-columns: repeat(3, 1fr); }}
      .topbar {{ display: block; }}
      .status-pill {{ text-align: left; margin-top: 18px; }}
      .metric, .wide, .sidepanel {{ grid-column: 1 / -1; }}
      .main {{ padding: 22px; }}
    }}
    @media (max-width: 640px) {{
      .nav {{ grid-template-columns: 1fr; }}
      .grid {{ gap: 10px; }}
      .panel {{ padding: 15px; }}
      h2 {{ font-size: 34px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside class="side">
      <div class="brand">
        <div class="mark">CW</div>
        <div>
          <h1>Codex Writer</h1>
          <span>Local Story Operations</span>
        </div>
      </div>
      <nav class="nav">
        <a href="#overview">总览</a>
        <a href="#chapters">章节</a>
        <a href="#review">审查</a>
        <a href="#memory">记忆</a>
        <a href="#reading">追读力</a>
        <a href="#entities">实体</a>
      </nav>
    </aside>
    <main class="main">
      <section class="topbar" id="overview">
        <div>
          <div class="eyebrow">Project Dashboard</div>
          <h2>{escape(str(p.get('title') or '未命名作品'))}</h2>
          <div class="subtitle">
            {escape(str(p.get('genre') or '未设置类型'))} · 第 {p.get('current_volume', 1)} 卷 · 第 {current_chapter} 章 · RAG {escape(str(p.get('rag_mode') or 'bm25'))}
          </div>
        </div>
        <div class="status-pill">
          <strong class="{health_class}">{health_label}</strong>
          <span>{escape(str(p.get('story_status') or 'unknown'))}</span>
        </div>
      </section>

      <section class="grid">
        <div class="panel metric">
          <div class="label">总字数</div>
          <div class="number">{total_words:,}</div>
          <div class="meta">当前累计正文规模</div>
        </div>
        <div class="panel metric">
          <div class="label">章节完成</div>
          <div class="number">{progress_label}</div>
          <div class="bar"><span></span></div>
        </div>
        <div class="panel metric">
          <div class="label">审查阻断</div>
          <div class="number {health_class}">{review.get('total_blocking', 0)}</div>
          <div class="meta">阻断为 0 才建议继续主线写入</div>
        </div>
        <div class="panel metric">
          <div class="label">追读债务</div>
          <div class="number">{reading_power.get('open', 0)} <small>open</small></div>
          <div class="meta">过期 {reading_power.get('expired', 0)} · 已兑现 {reading_power.get('paid', 0)}</div>
        </div>

        <div class="panel wide" id="chapters">
          <div class="label">最近章节网格</div>
          <div class="chapter-grid">
            {chapter_tiles}
          </div>
        </div>
        <div class="panel sidepanel" id="review">
          <div class="label">审查概况</div>
          <div class="number">{review.get('total_reviews', 0)} <small>reviews</small></div>
          <div class="meta">Rejected: {rejected} · Accepted: {accepted}</div>
          <div class="list" style="margin-top: 18px;">{severity_rows}</div>
        </div>

        <div class="panel sidepanel" id="memory">
          <div class="label">记忆系统</div>
          <div class="row"><strong>活跃片段</strong><span>{memory.get('episodic_active', 0)}</span></div>
          <div class="row"><strong>归档片段</strong><span>{memory.get('episodic_archived', 0)}</span></div>
          <div class="row"><strong>长期记忆</strong><span>{memory.get('semantic_total', 0)}</span></div>
          <div class="row"><strong>冲突记录</strong><span>{memory.get('conflicts_total', 0)}</span></div>
        </div>
        <div class="panel sidepanel" id="reading">
          <div class="label">追读力</div>
          <div class="row"><strong>开放债务</strong><span>{reading_power.get('open', 0)}</span></div>
          <div class="row"><strong>已兑现</strong><span>{reading_power.get('paid', 0)}</span></div>
          <div class="row"><strong>已过期</strong><span>{reading_power.get('expired', 0)}</span></div>
          <div class="row"><strong>最老未兑现</strong><span>Ch.{reading_power.get('oldest_open', 0)}</span></div>
        </div>
        <div class="panel sidepanel" id="entities">
          <div class="label">实体投影</div>
          <div class="list">{entity_rows}</div>
        </div>
      </section>
      <div class="footer">Generated by Codex Writer · 只读面板，不修改项目状态</div>
    </main>
  </div>
</body>
</html>
"""


def _chapter_tile(chapter: dict) -> str:
    status = str(chapter.get("status") or "unknown")
    klass = "accepted" if status == "accepted" else "rejected" if status == "rejected" else ""
    return f"""
<div class="chapter {klass}">
  <div class="chapter-num">第{int(chapter.get('chapter', 0) or 0):04d}章</div>
  <div class="chapter-title">{escape(str(chapter.get('title') or '未命名章节'))}</div>
  <div class="chapter-foot"><span>{escape(status)}</span><span>{int(chapter.get('word_count', 0) or 0)}字</span></div>
</div>"""


def _entity_row(entity: dict) -> str:
    return (
        '<div class="row">'
        f"<strong>{escape(str(entity.get('name') or '未命名'))}</strong>"
        f"<span>{escape(str(entity.get('type') or 'unknown'))}</span>"
        "</div>"
    )


def _severity_rows(by_severity: dict) -> str:
    if not by_severity:
        return '<div class="empty">暂无审查问题</div>'
    return "".join(
        '<div class="row">'
        f"<strong>{escape(str(severity))}</strong>"
        f"<span>{count}</span>"
        "</div>"
        for severity, count in sorted(by_severity.items())
    )


def _pct(part: int, whole: int) -> int:
    if whole <= 0:
        return 0
    return max(0, min(100, round(part / whole * 100)))


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
