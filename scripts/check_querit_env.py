"""诊断脚本：检查 Querit 环境变量配置
用法：python scripts/check_querit_env.py
不打印真实 API Key。
"""
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from env_loader import load_env, get_env_bool
import os

# 加载 .env
load_env()

env_file = Path(__file__).parent.parent / ".env"

print("\n=== Querit 环境配置诊断 ===\n")
print(f".env 路径:        {env_file}")
print(f".env 存在:        {env_file.exists()}")
print()
print(f"QUERIT_MOCK_MODE 原始值:  {os.environ.get('QUERIT_MOCK_MODE', '(未设置)')!r}")
print(f"QUERIT_MOCK_MODE 解析值:  {get_env_bool('QUERIT_MOCK_MODE', default=True)}")
print()
print(f"QUERIT_API_BASE_URL:      {os.environ.get('QUERIT_API_BASE_URL', '(未设置)')}")
print(f"QUERIT_API_SEARCH_PATH:   {os.environ.get('QUERIT_API_SEARCH_PATH', '(未设置)')}")
print(f"QUERIT_API_KEY 已设置:    {bool(os.environ.get('QUERIT_API_KEY'))}")
print()

# 最终判断
mock = get_env_bool("QUERIT_MOCK_MODE", default=True)
if mock:
    print("结论：当前为 Mock 测试模式。")
else:
    key_ok = bool(os.environ.get("QUERIT_API_KEY"))
    url_ok = bool(os.environ.get("QUERIT_API_BASE_URL"))
    if key_ok and url_ok:
        print("结论：当前为真实 API 模式，配置完整。")
    else:
        missing = []
        if not key_ok:
            missing.append("QUERIT_API_KEY")
        if not url_ok:
            missing.append("QUERIT_API_BASE_URL")
        print(f"结论：真实 API 模式，但配置不完整，缺少：{', '.join(missing)}")
