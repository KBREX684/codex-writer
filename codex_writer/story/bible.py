from __future__ import annotations

import copy
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codex_writer.core.io import read_json, write_json_atomic, write_markdown_atomic
from codex_writer.core.paths import novel_bible_markdown_path, novel_bible_path


SCHEMA_VERSION = "codex-writer/novel-bible/v1"
MIN_TARGET_WORDS = 1_000_000
MIN_TARGET_CHAPTERS = 300
MIN_VOLUME_COUNT = 5


REQUIRED_TEXT_PATHS = (
    "sections.project_positioning.one_sentence_positioning",
    "sections.project_positioning.commercial_hook",
    "sections.global_story.main_goal",
    "sections.global_story.core_conflict",
    "sections.global_story.hidden_line",
    "sections.global_story.endgame",
    "sections.world_system.geography",
    "sections.world_system.social_order",
    "sections.world_system.resource_economy",
    "sections.power_system.system_type",
    "sections.power_system.breakthrough_rules",
    "sections.power_system.costs_and_limits",
    "sections.character_system.protagonist.name",
    "sections.character_system.protagonist.desire",
    "sections.character_system.protagonist.flaw",
    "sections.character_system.protagonist.arc",
    "sections.golden_finger.type",
    "sections.golden_finger.boundary",
    "sections.plot_threads.main_thread",
    "sections.reading_power.payoff_cadence",
    "sections.style_contract.voice",
    "sections.runtime_contract.chapter_brief_policy",
)

REQUIRED_LIST_PATHS = (
    "sections.project_positioning.reader_promise",
    "sections.global_story.phase_milestones",
    "sections.volume_roadmap.volumes",
    "sections.world_system.factions",
    "sections.world_system.hard_rules",
    "sections.power_system.realms",
    "sections.character_system.antagonist_tiers",
    "sections.character_system.relationship_map",
    "sections.golden_finger.costs",
    "sections.plot_threads.foreshadowing",
    "sections.reading_power.cool_point_cycles",
    "sections.reading_power.hook_strategy",
    "sections.style_contract.anti_ai_rules",
    "sections.style_contract.forbidden_patterns",
    "sections.runtime_contract.review_rules",
)

VOLUME_REQUIRED_FIELDS = (
    "volume",
    "title",
    "chapters",
    "target_words",
    "core_conflict",
    "climax",
    "upgrade_node",
    "antagonist_tier",
    "reader_promise",
    "ending_hook",
)


def create_novel_bible_template(
    title: str,
    genre: str,
    *,
    target_words: int = MIN_TARGET_WORDS,
    target_chapters: int = 500,
    volume_count: int = 6,
) -> dict:
    volume_count = max(MIN_VOLUME_COUNT, int(volume_count or 0))
    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": "",
        },
        "book": {
            "title": title,
            "genre": genre,
        },
        "target_scale": {
            "target_words": int(target_words),
            "target_chapters": int(target_chapters),
            "volume_count": volume_count,
            "chapters_per_volume": _chapters_per_volume(int(target_chapters), volume_count),
        },
        "approval": {
            "status": "draft",
            "approved_at": "",
            "approved_by": "",
            "notes": "",
        },
        "sections": {
            "project_positioning": {
                "one_sentence_positioning": "",
                "target_platform": "",
                "target_reader": "",
                "commercial_hook": "",
                "reader_promise": [],
                "content_rating": "",
                "anti_trope": "",
            },
            "global_story": {
                "main_goal": "",
                "core_conflict": "",
                "hidden_line": "",
                "endgame": "",
                "theme": "",
                "story_engine": "",
                "phase_milestones": [],
            },
            "volume_roadmap": {
                "strategy": "百万字长篇按卷推进，每卷先锁定卷目标、卷末高潮、升级节点和跨卷伏笔，再拆章。",
                "volumes": [],
            },
            "world_system": {
                "geography": "",
                "factions": [],
                "social_order": "",
                "resource_economy": "",
                "history_timeline": [],
                "hard_rules": [],
                "taboos": [],
            },
            "power_system": {
                "system_type": "",
                "realms": [],
                "subtiers": [],
                "breakthrough_rules": "",
                "costs_and_limits": "",
                "combat_rules": [],
                "counter_rules": [],
            },
            "character_system": {
                "protagonist": {
                    "name": "",
                    "desire": "",
                    "flaw": "",
                    "arc": "",
                    "methods": "",
                    "ooc_forbidden": [],
                },
                "allies": [],
                "antagonist_tiers": [],
                "relationship_map": [],
            },
            "golden_finger": {
                "type": "",
                "name": "",
                "visibility": "",
                "boundary": "",
                "growth_rhythm": "",
                "costs": [],
                "failure_conditions": [],
                "counterplay": [],
            },
            "plot_threads": {
                "main_thread": "",
                "secondary_threads": [],
                "foreshadowing": [],
                "open_loop_policy": "",
            },
            "reading_power": {
                "payoff_cadence": "",
                "pressure_release_ratio": "",
                "strand_strategy": "",
                "cool_point_cycles": [],
                "hook_strategy": [],
            },
            "style_contract": {
                "voice": "",
                "style_priority": "",
                "dialogue_rules": [],
                "anti_ai_rules": [],
                "forbidden_patterns": [],
            },
            "runtime_contract": {
                "chapter_brief_policy": "",
                "review_rules": [],
                "commit_rules": [],
            },
        },
    }


def create_demo_bible(
    title: str,
    genre: str,
    *,
    target_words: int = MIN_TARGET_WORDS,
    target_chapters: int = 500,
    volume_count: int = 6,
) -> dict:
    bible = create_novel_bible_template(
        title,
        genre,
        target_words=target_words,
        target_chapters=target_chapters,
        volume_count=volume_count,
    )
    chapters_per_volume = bible["target_scale"]["chapters_per_volume"]
    words_per_volume = max(1, int(target_words) // max(1, int(volume_count)))
    volumes = []
    for index in range(1, int(volume_count) + 1):
        start = (index - 1) * chapters_per_volume + 1
        end = min(index * chapters_per_volume, int(target_chapters))
        if start > int(target_chapters):
            start = end = int(target_chapters)
        volumes.append(
            {
                "volume": index,
                "title": f"第{index:03d}卷 长线推进",
                "chapters": f"第{start}-{end}章",
                "target_words": words_per_volume,
                "core_conflict": f"第{index}阶段核心敌人与资源压力逐级升级。",
                "climax": f"第{index}卷末完成一次地位、力量或真相的大兑现。",
                "upgrade_node": f"主角获得第{index}阶段能力/资源，但必须支付明确代价。",
                "antagonist_tier": f"第{index}层反派镜像主角的欲望或缺陷。",
                "reader_promise": f"本卷持续兑现成长、压迫反打和世界真相推进。",
                "ending_hook": f"卷末留下通往第{index + 1}卷的新问题或更高层敌人。",
            }
        )

    sections = bible["sections"]
    sections["project_positioning"].update(
        {
            "one_sentence_positioning": f"《{title}》是一部以{genre}为核心的百万字长篇，靠清晰升级、强因果和持续伏笔回收驱动追读。",
            "target_platform": "中文长篇连载平台",
            "target_reader": "偏好长线升级、强规则世界、阶段性爽点和持续悬念的读者",
            "commercial_hook": "主角在硬规则压迫下逐步反打，每卷都有可感知的地位变化和更高层真相。",
            "reader_promise": ["稳定升级", "持续压迫反打", "跨卷伏笔回收", "世界规则越揭越深"],
            "content_rating": "大众向",
            "anti_trope": "不靠无解释奇遇跳级，所有胜利都必须有代价、铺垫或规则依据。",
        }
    )
    sections["global_story"].update(
        {
            "main_goal": "主角从低位困局出发，逐步夺回命运解释权并重写世界规则。",
            "core_conflict": "个人成长目标与既有秩序、资源垄断、隐秘势力之间的长期冲突。",
            "hidden_line": "早期看似局部的敌意背后，存在跨卷延伸的旧案、规则漏洞或上层博弈。",
            "endgame": "终局必须同时兑现主角成长、核心暗线、世界规则真相和最大反派镜像对抗。",
            "theme": "人在强规则世界中如何付出代价并夺回选择权。",
            "story_engine": "每卷用资源压力推动行动，用敌人升级制造压迫，用伏笔回收带来认知跃迁。",
            "phase_milestones": [
                "开局立下不可逆目标",
                "第一卷完成弱势求生与核心资源发现",
                "中期打开更大地图并暴露暗线",
                "后期让主角面对与自己相似的镜像道路",
                "终局回收世界规则根因",
            ],
        }
    )
    sections["volume_roadmap"]["volumes"] = volumes
    sections["world_system"].update(
        {
            "geography": "世界按低位区域、核心区域、禁区和更高层空间递进展开，每次换地图都带来新规则和新资源。",
            "factions": ["底层家族/城池", "中层宗门/学院", "资源垄断势力", "隐藏旧案相关势力", "终局秩序制定者"],
            "social_order": "地位由资源、血脉/资质、功绩和规则解释权共同决定，底层无法轻易越过制度门槛。",
            "resource_economy": "核心资源稀缺且可被垄断；主角每次获得资源都必须面对交易、敌意或代价。",
            "history_timeline": ["旧秩序建立", "关键规则被篡改或垄断", "主角开局遭遇规则压迫", "暗线逐卷浮出"],
            "hard_rules": ["新地图必须带来新限制", "高阶资源必须有来源", "势力行为必须服务利益或恐惧"],
            "taboos": ["无代价跳级", "临时新增万能势力救场", "敌人只为送经验而行动"],
        }
    )
    sections["power_system"].update(
        {
            "system_type": "境界/资源/规则三轨并行",
            "realms": ["入门", "筑基", "成势", "破境", "掌域", "问道", "终局境"],
            "subtiers": ["初期", "中期", "后期", "圆满"],
            "breakthrough_rules": "突破需要资源、认知和身体/精神承载力三者同时满足。",
            "costs_and_limits": "越级行动会消耗寿命、根基、关系债或暴露秘密，不能免费反复使用。",
            "combat_rules": ["境界压制有效但可被规则漏洞和准备反制", "能力克制优先于单纯数值", "战斗结果必须改变局面"],
            "counter_rules": ["敌人会研究主角能力", "金手指有被误判、封锁或诱导的风险"],
        }
    )
    sections["character_system"].update(
        {
            "protagonist": {
                "name": "待命名主角",
                "desire": "夺回被规则、敌人或命运剥夺的选择权。",
                "flaw": "过度依赖计算和忍耐，容易把情感债务压到后期爆发。",
                "arc": "从只求自保，到敢于承担更大秩序的重写代价。",
                "methods": "观察规则、积累资源、制造信息差、在关键时刻反打。",
                "ooc_forbidden": ["无铺垫圣母", "无代价鲁莽", "明知规则仍无理由硬闯"],
            },
            "allies": [
                {"role": "早期盟友", "function": "提供情感锚点与底层视角"},
                {"role": "中期盟友", "function": "打开更大势力网络"},
                {"role": "后期盟友", "function": "逼主角承担秩序选择"},
            ],
            "antagonist_tiers": [
                {"tier": "小反派", "function": "压迫开局、制造羞辱与资源缺口"},
                {"tier": "中反派", "function": "掌握局部规则并反制主角能力"},
                {"tier": "大反派", "function": "镜像主角道路，证明另一种选择的诱惑"},
            ],
            "relationship_map": ["主角-盟友：利益起步，债务加深", "主角-反派：同欲望不同代价", "主角-势力：被压迫者到规则挑战者"],
        }
    )
    sections["golden_finger"].update(
        {
            "type": "克制型辅助能力",
            "name": "待命名金手指",
            "visibility": "早期仅主角知道，中期被部分敌人误判，后期成为可被针对的公开变量。",
            "boundary": "只能提供信息差、推演或资源转化，不能直接替主角完成情感、战斗和选择。",
            "growth_rhythm": "每卷解锁一个新用途，同时引入一个新代价或新风险。",
            "costs": ["消耗资源", "暴露线索", "留下关系债", "增加敌人反制样本"],
            "failure_conditions": ["信息不足", "规则被敌人篡改", "主角身体/精神承载不足"],
            "counterplay": ["敌人诱导错误输入", "封锁资源来源", "利用主角缺陷制造选择困局"],
        }
    )
    sections["plot_threads"].update(
        {
            "main_thread": "主角逐卷突破压迫、获得资源、揭开旧案并靠代价重写规则。",
            "secondary_threads": ["盟友债务线", "世界规则真相线", "反派镜像线", "金手指代价线"],
            "foreshadowing": [
                {"content": "开局异常规则", "plant": "前10章", "payoff": "第2-3卷"},
                {"content": "主角能力代价", "plant": "第1卷", "payoff": "中期反制"},
                {"content": "终局秩序旧案", "plant": "第1-2卷", "payoff": "后期"},
            ],
            "open_loop_policy": "每卷必须新增、推进、回收至少一组开放环，禁止只埋不收。",
        }
    )
    sections["reading_power"].update(
        {
            "payoff_cadence": "每章至少有目标/代价/关系/信息变化之一；每5章有组合爽点，每10-15章有地位或认知里程碑。",
            "pressure_release_ratio": "常规卷压4扬6，关键低谷卷压6扬4，卷末集中兑现。",
            "strand_strategy": "主线推进为主，感情/关系线和世界观线定期穿插，避免连续纯任务推进。",
            "cool_point_cycles": ["示弱-积压-反打-余波", "信息差-误判-揭示-新债", "资源缺口-冒险-获得-代价"],
            "hook_strategy": ["危机钩", "选择钩", "渴望钩", "真相钩"],
        }
    )
    sections["style_contract"].update(
        {
            "voice": "克制、具体、有压迫感，少解释，多用行动和代价呈现人物判断。",
            "style_priority": "因果清晰 > 压迫升级 > 爽点兑现 > 余味留白",
            "dialogue_rules": ["对白必须带意图冲突", "减少纯说明", "允许沉默、打断和答非所问"],
            "anti_ai_rules": ["删段末感悟句", "少用缓缓/淡淡/微微", "情绪用动作和生理反应", "展示后不解释"],
            "forbidden_patterns": ["安全着陆式章末", "万能高人救场", "无代价升级", "重复模板化神态"],
        }
    )
    sections["runtime_contract"].update(
        {
            "chapter_brief_policy": "章节任务书必须从圣经、卷合同、章纲、最近提交中生成，主助手不得手写替代 planning_agent。",
            "review_rules": ["必须检查设定一致", "必须检查章纲覆盖", "必须检查AI味", "blocking 未清不得提交"],
            "commit_rules": ["写后事实只能通过 extraction/commit 进入投影", "开放环必须记录埋设与回收状态"],
        }
    )
    bible["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    return bible


def normalize_novel_bible(
    candidate: dict[str, Any],
    title: str,
    genre: str,
    *,
    target_words: int = MIN_TARGET_WORDS,
    target_chapters: int = 500,
    volume_count: int = 6,
) -> dict:
    base = create_novel_bible_template(
        title,
        genre,
        target_words=target_words,
        target_chapters=target_chapters,
        volume_count=volume_count,
    )
    merged = _deep_merge(base, candidate if isinstance(candidate, dict) else {})
    merged["meta"]["schema_version"] = SCHEMA_VERSION
    merged["meta"]["status"] = "draft"
    merged["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    merged["book"]["title"] = merged.get("book", {}).get("title") or title
    merged["book"]["genre"] = merged.get("book", {}).get("genre") or genre
    merged.setdefault("approval", {})
    merged["approval"]["status"] = "draft"
    merged["approval"].setdefault("approved_at", "")
    merged["approval"].setdefault("approved_by", "")
    merged["approval"].setdefault("notes", "")
    return merged


def validate_novel_bible(bible: dict[str, Any] | None) -> dict:
    missing: list[str] = []
    section_status: dict[str, bool] = {}
    if not isinstance(bible, dict):
        return {
            "ready": False,
            "content_ready": False,
            "approved": False,
            "missing": ["novel_bible"],
            "section_status": {},
        }

    if _get(bible, "meta.schema_version") != SCHEMA_VERSION:
        missing.append("meta.schema_version")
    target_words = _as_int(_get(bible, "target_scale.target_words"))
    target_chapters = _as_int(_get(bible, "target_scale.target_chapters"))
    if target_words < MIN_TARGET_WORDS:
        missing.append("target_scale.target_words>=1000000")
    if target_chapters < MIN_TARGET_CHAPTERS:
        missing.append("target_scale.target_chapters>=300")

    for path in REQUIRED_TEXT_PATHS:
        ok = _has_text(_get(bible, path))
        section_status[path] = ok
        if not ok:
            missing.append(path)
    for path in REQUIRED_LIST_PATHS:
        ok = _has_items(_get(bible, path))
        section_status[path] = ok
        if not ok:
            missing.append(path)

    volumes = _get(bible, "sections.volume_roadmap.volumes")
    if isinstance(volumes, list) and volumes:
        if len(volumes) < MIN_VOLUME_COUNT:
            missing.append(f"sections.volume_roadmap.volumes>={MIN_VOLUME_COUNT}")
        for index, volume in enumerate(volumes, start=1):
            if not isinstance(volume, dict):
                missing.append(f"sections.volume_roadmap.volumes[{index}]")
                continue
            for field in VOLUME_REQUIRED_FIELDS:
                value = volume.get(field)
                if not (_has_items(value) if isinstance(value, list) else _has_text(value) or isinstance(value, int)):
                    missing.append(f"sections.volume_roadmap.volumes[{index}].{field}")

    content_missing = [item for item in missing if item != "approval.status"]
    approved = _get(bible, "approval.status") == "approved"
    if not approved:
        missing.append("approval.status")
    seen = []
    for item in missing:
        if item not in seen:
            seen.append(item)
    content_ready = not content_missing
    return {
        "ready": content_ready and approved,
        "content_ready": content_ready,
        "approved": approved,
        "missing": seen,
        "section_status": section_status,
        "target_scale": bible.get("target_scale", {}),
    }


def load_novel_bible(project_root: Path) -> dict[str, Any] | None:
    path = novel_bible_path(project_root)
    if not path.exists():
        return None
    try:
        data = read_json(path)
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def write_novel_bible(project_root: Path, bible: dict[str, Any]) -> dict:
    report = validate_novel_bible(bible)
    path = novel_bible_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, bible)
    write_markdown_atomic(novel_bible_markdown_path(project_root), render_novel_bible_markdown(bible, report))
    return report


def approve_novel_bible(project_root: Path, *, approved_by: str = "author", notes: str = "") -> dict:
    bible = load_novel_bible(project_root)
    report = validate_novel_bible(bible)
    content_missing = [item for item in report["missing"] if item != "approval.status"]
    if content_missing:
        raise ValueError("novel bible content incomplete: " + ", ".join(content_missing))
    assert bible is not None
    bible = copy.deepcopy(bible)
    bible["approval"] = {
        **(bible.get("approval") or {}),
        "status": "approved",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": approved_by,
        "notes": notes,
    }
    bible.setdefault("meta", {})["status"] = "approved"
    bible["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    return write_novel_bible(project_root, bible)


def render_novel_bible_markdown(bible: dict[str, Any], report: dict | None = None) -> str:
    report = report or validate_novel_bible(bible)
    book = bible.get("book") or {}
    scale = bible.get("target_scale") or {}
    sections = bible.get("sections") or {}
    lines = [
        f"# {book.get('title', '')} 百万字创作圣经",
        "",
        f"- 题材：{book.get('genre', '')}",
        f"- 目标字数：{scale.get('target_words', '')}",
        f"- 目标章节：{scale.get('target_chapters', '')}",
        f"- 卷数：{scale.get('volume_count', '')}",
        f"- 审批状态：{(bible.get('approval') or {}).get('status', '')}",
        f"- 内容就绪：{report.get('content_ready')}",
        f"- 主链就绪：{report.get('ready')}",
        "",
    ]
    if report.get("missing"):
        lines.extend(["## 缺口", *[f"- {item}" for item in report["missing"]], ""])
    for section_name in (
        "project_positioning",
        "global_story",
        "volume_roadmap",
        "world_system",
        "power_system",
        "character_system",
        "golden_finger",
        "plot_threads",
        "reading_power",
        "style_contract",
        "runtime_contract",
    ):
        lines.extend(_render_section(section_name, sections.get(section_name) or {}))
    return "\n".join(lines).rstrip() + "\n"


def _render_section(name: str, data: Any) -> list[str]:
    title = {
        "project_positioning": "项目定位",
        "global_story": "全书主线",
        "volume_roadmap": "卷级路线图",
        "world_system": "世界系统",
        "power_system": "力量系统",
        "character_system": "人物系统",
        "golden_finger": "金手指系统",
        "plot_threads": "伏笔与剧情债务",
        "reading_power": "追读力系统",
        "style_contract": "写作裁决层",
        "runtime_contract": "运行时合同",
    }.get(name, name)
    lines = [f"## {title}"]
    if isinstance(data, dict):
        for key, value in data.items():
            lines.extend(_render_value(key, value, 0))
    else:
        lines.append(str(data))
    lines.append("")
    return lines


def _render_value(key: str, value: Any, indent: int) -> list[str]:
    prefix = "  " * indent
    label = f"{prefix}- {key}:"
    if isinstance(value, dict):
        lines = [label]
        for child_key, child_value in value.items():
            lines.extend(_render_value(child_key, child_value, indent + 1))
        return lines
    if isinstance(value, list):
        lines = [label]
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{prefix}  -")
                for child_key, child_value in item.items():
                    lines.extend(_render_value(child_key, child_value, indent + 2))
            else:
                lines.append(f"{prefix}  - {item}")
        return lines
    return [f"{label} {value}"]


def _deep_merge(base: dict, incoming: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _get(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_items(value: Any) -> bool:
    return isinstance(value, list) and any(item for item in value if item)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _chapters_per_volume(target_chapters: int, volume_count: int) -> int:
    if target_chapters <= 0 or volume_count <= 0:
        return 0
    return max(1, int(math.ceil(target_chapters / volume_count)))
