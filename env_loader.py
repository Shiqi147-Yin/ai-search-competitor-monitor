"""统一环境变量加载与布尔解析
在导入任何业务模块前加载 .env，确保所有模块读取到正确的环境变量。
"""
import os
import logging
from pathlib import Path

# 项目根目录（本文件所在目录）
_PROJECT_ROOT = Path(__file__).parent

logger = logging.getLogger(__name__)


def load_env() -> None:
    """从项目根目录加载 .env，已有环境变量优先（override=False）。"""
    env_file = _PROJECT_ROOT / ".env"
    try:
        from dotenv import load_dotenv
        if env_file.exists():
            load_dotenv(dotenv_path=env_file, override=False)
            logger.debug(f".env 已加载：{env_file}")
        else:
            logger.debug(f".env 不存在，跳过加载：{env_file}")
    except ImportError:
        logger.warning("python-dotenv 未安装，跳过 .env 加载；请运行 pip install python-dotenv")

    # 诊断输出（不打印 Key 值）
    logger.debug(
        "Querit config: mock_mode=%s base_url=%s search_path=%s api_key_set=%s",
        get_env_bool("QUERIT_MOCK_MODE", True),
        bool(os.environ.get("QUERIT_API_BASE_URL")),
        bool(os.environ.get("QUERIT_API_SEARCH_PATH")),
        bool(os.environ.get("QUERIT_API_KEY")),
    )


def get_env_bool(name: str, default: bool = False) -> bool:
    """统一布尔值解析。
    true/1/yes/on → True
    false/0/no/off → False
    缺失时使用 default。
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
