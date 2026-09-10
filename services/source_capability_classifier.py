"""来源能力分级器
根据抓取结果和来源平台判断能力等级（A/B/C）及建议处理方式。
等级可被人工覆盖，不写死。
"""
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "source_capabilities.yaml"

# 平台名 -> config key 映射
_PLATFORM_KEY_MAP = {
    "官网": "official_docs",
    "Blog": "official_blog",
    "GitHub": "github",
    "X": "x",
    "LinkedIn": "linkedin",
    "Discord": "discord",
    "Event": "event",
    "Other": "other",
}

_DEFAULT_CAPABILITIES = {
    "official_blog":  {"automation_level": "A", "default_action": "auto_fetch",            "fetch_strategy": "generic_web"},
    "official_docs":  {"automation_level": "A", "default_action": "auto_fetch",            "fetch_strategy": "generic_web"},
    "github":         {"automation_level": "B", "default_action": "github_analysis",       "fetch_strategy": "github_special"},
    "x":              {"automation_level": "B", "default_action": "try_fetch_then_manual", "fetch_strategy": "generic_web"},
    "linkedin":       {"automation_level": "C", "default_action": "manual_supplement",     "fetch_strategy": "manual_fallback"},
    "discord":        {"automation_level": "C", "default_action": "manual_supplement",     "fetch_strategy": "manual_fallback"},
    "event":          {"automation_level": "B", "default_action": "try_fetch_then_manual", "fetch_strategy": "generic_web"},
    "other":          {"automation_level": "B", "default_action": "try_fetch_then_manual", "fetch_strategy": "generic_web"},
}


def _load_capabilities() -> dict:
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("sources", {})
    except Exception:
        return {}


@dataclass
class CapabilityResult:
    automation_level: str           # A / B / C
    default_action: str             # auto_fetch / github_analysis / try_fetch_then_manual / manual_supplement
    needs_manual: bool
    reason: str
    suggestion: str
    override_applied: bool = False  # 是否使用了人工覆盖等级


# 建议处理方式文案
_ACTION_SUGGESTION = {
    "auto_fetch":             "自动抓取后进入待审核区，补充分析字段即可",
    "github_analysis":        "自动抓取并运行 GitHub 专项分析，确认变更字段后进入待审核区",
    "try_fetch_then_manual":  "尝试自动抓取；若失败请人工补充标题、发布时间和摘要",
    "manual_supplement":      "该来源通常受登录限制，请人工填写标题、发布时间和动态概述",
}

# C 级来源需要人工补充的字段
_MANUAL_FIELDS_NEEDED = {
    "C": ["title", "publish_date", "summary"],
    "B": ["publish_date", "summary"],
    "A": [],
}


def classify_fetch_result(
    fetch_status: str,
    has_title: bool,
    has_description: bool,
    has_published_date: bool,
    source_platform: str = "Other",
    override_level: Optional[str] = None,
) -> CapabilityResult:
    """根据抓取结果和来源平台判断能力等级。

    override_level: 人工覆盖等级，传入则跳过自动判断规则直接使用该值。
    """
    caps = _load_capabilities()
    key = _PLATFORM_KEY_MAP.get(source_platform, "other")
    cap_cfg = caps.get(key) or _DEFAULT_CAPABILITIES.get(key, {})
    config_level = cap_cfg.get("automation_level", "B")
    config_action = cap_cfg.get("default_action", "try_fetch_then_manual")

    if override_level:
        level = override_level
        override_applied = True
    else:
        if fetch_status in ("restricted",):
            # GitHub restricted 是 rate limit，不降到 C
            if source_platform == "GitHub":
                level = "B"
            else:
                level = "C"
        elif fetch_status == "failed":
            # X/LinkedIn/Discord 网络失败维持 C 级；其他来源降为 B
            level = config_level if config_level == "C" else "B"
        elif fetch_status in ("success",) and has_title and has_description:
            level = "A"
        elif fetch_status in ("success", "partial") and has_title:
            level = "B"
        elif fetch_status == "partial" and not has_title:
            level = "C" if config_level == "C" else "B"
        else:
            level = config_level
        override_applied = False

    needs_manual = level in ("B", "C") or not has_title or not has_published_date

    # 原因描述
    if fetch_status == "restricted":
        reason = "页面受访问限制（403/401/429），无法自动抓取内容"
    elif fetch_status == "failed":
        reason = "网络连接失败（ConnectTimeout / ConnectionError 等）"
    elif not has_title:
        reason = "抓取成功但未能提取标题"
    elif not has_published_date:
        reason = "抓取成功，标题已提取，但未能识别发布时间"
    else:
        reason = "抓取完整"

    suggestion = _ACTION_SUGGESTION.get(config_action, config_action)
    if level == "C":
        suggestion = _ACTION_SUGGESTION["manual_supplement"]
    elif level == "B" and fetch_status == "failed":
        suggestion = _ACTION_SUGGESTION["try_fetch_then_manual"]

    return CapabilityResult(
        automation_level=level,
        default_action=config_action,
        needs_manual=needs_manual,
        reason=reason,
        suggestion=suggestion,
        override_applied=override_applied,
    )


def get_platform_capability(source_platform: str) -> dict:
    """返回指定平台的能力配置字典（直接来自 YAML）。"""
    caps = _load_capabilities()
    key = _PLATFORM_KEY_MAP.get(source_platform, "other")
    return caps.get(key) or _DEFAULT_CAPABILITIES.get(key, {})


def get_fetch_strategy(source_platform: str) -> str:
    """返回指定平台的推荐抓取策略。"""
    cap = get_platform_capability(source_platform)
    return cap.get("fetch_strategy", "generic_web")


def list_all_capabilities() -> dict:
    """返回所有来源的能力配置，用于页面展示。"""
    caps = _load_capabilities()
    result = {}
    for platform, key in _PLATFORM_KEY_MAP.items():
        cfg = caps.get(key) or _DEFAULT_CAPABILITIES.get(key, {})
        result[platform] = {
            "automation_level": cfg.get("automation_level", "B"),
            "default_action": cfg.get("default_action", "try_fetch_then_manual"),
            "description": cfg.get("description", ""),
        }
    return result
