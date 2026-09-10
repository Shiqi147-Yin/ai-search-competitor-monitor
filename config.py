"""全局配置：路径、枚举常量、字段映射"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent

# 数据库路径
DB_PATH = BASE_DIR / "data" / "competitor_dashboard.db"

# Excel 模板路径
TEMPLATE_PATH = BASE_DIR / "templates" / "competitor_updates_template.xlsx"

# ── 枚举常量 ──────────────────────────────────────────────────

COMPETITORS = ["Tavily", "Exa", "Brave", "Querit", "Other"]

CATEGORIES = ["产品与功能", "生态与集成", "市场与运营", "待评估"]

SOURCE_PLATFORMS = ["官网", "Blog", "GitHub", "X", "LinkedIn", "Discord", "Reddit", "YouTube", "Event", "第三方Blog", "Other"]

QUERIT_STATUS_OPTIONS = ["已覆盖", "部分覆盖", "推进中", "待评估", "暂无", "不跟进"]

PRIORITY_OPTIONS = ["高", "中", "低"]

REVIEW_STATUS_OPTIONS = ["待审核", "已确认", "已忽略"]

FOLLOW_UP_STATUS_OPTIONS = ["待处理", "推进中", "已完成", "无需处理"]

SOURCE_MODES = ["manual_excel", "querit_api"]

# ── Querit API 配置（全部运行时从环境变量读取，使用 get_env_bool 解析布尔值）──
# 注意：不在模块级固化，config.py 被 import 时 .env 可能尚未加载。
# 应通过 env_loader.get_env_bool / os.environ.get 运行时读取。
# 以下仅保留静态路径配置。

# 配置文件路径
QUERIT_SEARCH_CONFIG = BASE_DIR / "config" / "querit_search.yaml"
QUERIT_QUERY_TEMPLATES = BASE_DIR / "config" / "querit_query_templates.yaml"

# ── Excel 字段映射 ────────────────────────────────────────────

# Excel 列名 → 数据库字段名
EXCEL_COLUMN_MAP = {
    "发布时间": "publish_date",
    "竞品": "competitor",
    "动态标题": "title",
    "动态概述": "summary",
    "原始链接": "source_url",
    "信息平台": "source_platform",
    "备注": "gap_analysis",
}

# 必须存在的 Excel 列名
EXCEL_REQUIRED_COLUMNS = list(EXCEL_COLUMN_MAP.keys())

# 必须有值的数据库字段
REQUIRED_FIELDS = ["title", "source_url"]
