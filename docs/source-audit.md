# 源码核验与验证记录

本仓库的功能介绍根据完整原始应用代码核验，以下结论可在对应实现中查证。

| 核验项目 | 当前结论 | 实现依据 |
| --- | --- | --- |
| 可运行性 | 已提供入口、七个页面、数据库和依赖 | `app.py`、`pages/`、`database.py`、`requirements.txt` |
| 自动分析 | 规则与置信度分析已实现；真实模型事件合成尚未实现 | `services/content_analyzer.py`、`services/github_event_synthesizer.py` |
| 质量检查范围 | 手工导入、检索与官方巡检各有处理管线 | 三个入口页面及对应服务 |
| 示例数据 | 使用正式数据库支持的字段和中文枚举；明确标为虚构 | `demo/sample_updates.json`、`config.py`、`database.py` |
| 周次逻辑 | 周看板按 `week_id` 与已确认状态过滤；不等同于原文发布日期归周 | `get_weekly_dashboard`、`adapt_result`、`item_to_record` |
| 外部连接 | 真实 Querit API 和实时来源召回率未在本次核验中验证 | 测试使用 Mock、夹具与本地数据库 |
| 测试 | Python 3.12 下 774 项自动化测试通过，Streamlit 首页及七个功能页初始运行检查通过 | `python -m pytest tests/ -q` 与本地启动检查 |

## 发布整理

- 从原始压缩包恢复正确的中文页面文件名。
- 加入 `.gitignore` 与空密钥 `.env.example`，公开文件不包含原始 `.env`、私人数据库、虚拟环境、缓存和编辑器会话。
- 增加测试会话夹具，通过临时 SQLite 数据库支持全新克隆；测试不依赖原有运行数据。
- 按实际实现修订 README、产品设计、架构说明及示例字段，避免将接口预留或未经验证的效果描述为已完成能力。
- 保留原始业务功能与诊断工具；未重新设计业务逻辑。

`config/*.example.yaml` 是早期展示配置，运行服务读取对应的非 `.example` 文件。配置中的历史竞品事件用于开发评测，不表示已经完成实时新闻核验。
