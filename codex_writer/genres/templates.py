from __future__ import annotations

from copy import deepcopy


GENRE_TEMPLATES: tuple[dict, ...] = (
    {
        "name": "玄幻",
        "aliases": ["修仙", "仙侠", "东方玄幻", "升级流"],
        "core_promises": ["升级反馈清晰", "战力规则稳定", "强敌压迫递进"],
        "style_guidance": [
            "每章至少给出一个可感知爽点或战力变化。",
            "境界、功法、资源消耗必须前后一致，避免临场改规则。",
            "结尾优先落在新敌人、新资源、新代价或身份反转上。",
        ],
        "opening_hooks": ["弱势处境", "资源被夺", "隐藏天赋暴露", "宗门考核"],
        "review_focus": ["战力闭环", "升级节奏", "设定一致性", "爽点兑现"],
        "routing_hints": {"draft_agent": "draft_agent", "review_agent": "review_agent", "data_agent": "extract_agent"},
    },
    {
        "name": "都市脑洞",
        "aliases": ["都市异能", "都市系统", "脑洞文"],
        "core_promises": ["现实场景反差", "能力边界好懂", "短周期打脸反馈"],
        "style_guidance": [
            "用日常场景承接超常设定，先让读者看懂反差。",
            "系统、异能或金手指必须有明确限制和代价。",
            "章节结尾保留新的社会关系压力或能力误用后果。",
        ],
        "opening_hooks": ["职场羞辱", "家庭压力", "系统触发", "身份错位"],
        "review_focus": ["脑洞清晰度", "现实锚点", "反差爽点", "能力边界"],
        "routing_hints": {"draft_agent": "draft_agent", "review_agent": "review_agent", "data_agent": "extract_agent"},
    },
    {
        "name": "规则怪谈",
        "aliases": ["怪谈", "规则类", "诡异规则"],
        "core_promises": ["规则可推理", "违规则有后果", "信息差持续推进"],
        "style_guidance": [
            "规则必须可被读者复盘，不能靠作者临时宣布答案。",
            "每章至少推进一条规则验证、误导或反证。",
            "恐怖感优先来自规则矛盾和选择压力，不靠堆形容词。",
        ],
        "opening_hooks": ["陌生规则纸条", "倒计时", "同伴违规", "安全区失效"],
        "review_focus": ["规则自洽", "推理公平", "悬疑递进", "恐怖克制"],
        "routing_hints": {"draft_agent": "draft_agent", "review_agent": "review_agent", "data_agent": "extract_agent"},
    },
    {
        "name": "狗血言情",
        "aliases": ["现言", "豪门", "追妻", "虐恋"],
        "core_promises": ["关系张力高", "误会可追踪", "情绪债可偿还"],
        "style_guidance": [
            "每章推进一段明确的关系变化：靠近、误会、亏欠或决裂。",
            "误会必须有角色动机和信息来源，避免纯工具化。",
            "高情绪场面要落到动作、选择和代价，不只写心理独白。",
        ],
        "opening_hooks": ["重逢", "契约关系", "身份误判", "背叛证据"],
        "review_focus": ["情绪债", "误会链", "关系推进", "角色尊严"],
        "routing_hints": {"draft_agent": "draft_agent", "review_agent": "review_agent", "data_agent": "extract_agent"},
    },
    {
        "name": "古言",
        "aliases": ["古代言情", "宫斗", "宅斗", "权谋言情"],
        "core_promises": ["礼法压力", "身份秩序", "情感与利益冲突"],
        "style_guidance": [
            "把情感选择放进礼法、家族、权力结构中承压。",
            "称谓、身份、场合规矩要稳定，避免现代口吻出戏。",
            "章节钩子优先落在身份风险、利益交换或旧案线索上。",
        ],
        "opening_hooks": ["赐婚", "退亲", "入宫", "旧案重提"],
        "review_focus": ["时代口吻", "权力关系", "礼法约束", "情感动机"],
        "routing_hints": {"draft_agent": "draft_agent", "review_agent": "review_agent", "data_agent": "extract_agent"},
    },
    {
        "name": "现实题材",
        "aliases": ["现实主义", "行业文", "年代文", "职场现实"],
        "core_promises": ["问题真实", "成长可信", "行业细节有质感"],
        "style_guidance": [
            "冲突要来自制度、行业、家庭或选择压力，而非单纯巧合。",
            "细节优先服务人物选择，不堆资料。",
            "章节结尾保留新的现实难题或人物价值选择。",
        ],
        "opening_hooks": ["关键失败", "行业门槛", "家庭压力", "资源断裂"],
        "review_focus": ["现实可信度", "行业细节", "人物成长", "议题克制"],
        "routing_hints": {"draft_agent": "draft_agent", "review_agent": "review_agent", "data_agent": "extract_agent"},
    },
)


def _norm(value: str) -> str:
    return "".join(str(value or "").lower().split())


def list_genre_templates() -> list[dict]:
    return [deepcopy(item) for item in GENRE_TEMPLATES]


def match_genre_template(genre: str) -> dict | None:
    wanted = _norm(genre)
    if not wanted:
        return None
    for template in GENRE_TEMPLATES:
        names = [template["name"], *template.get("aliases", [])]
        if any(_norm(name) == wanted or _norm(name) in wanted or wanted in _norm(name) for name in names):
            return deepcopy(template)
    return None


def get_genre_template(genre: str) -> dict:
    template = match_genre_template(genre)
    if template is None:
        raise KeyError(genre)
    return template


def apply_template_to_brief(brief: dict, template: dict) -> dict:
    updated = deepcopy(brief)
    guidance = list(updated.get("style_guidance", []))
    for item in template.get("style_guidance", []):
        if item not in guidance:
            guidance.append(item)
    updated["style_guidance"] = guidance[:6]

    reminders = list(updated.get("anti_ai_reminders", []))
    for item in template.get("review_focus", [])[:3]:
        text = f"审查重点：{item}"
        if text not in reminders:
            reminders.append(text)
    updated["anti_ai_reminders"] = reminders[:6]
    updated.setdefault("genre_template", template.get("name", ""))
    return updated
