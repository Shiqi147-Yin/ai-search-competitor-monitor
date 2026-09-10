> **历史文档**：这是原始压缩包中的早期说明，部分功能与字段已变化。当前运行方式、能力和限制请以 [主 README](../README.md) 及源码为准。

# AI Agent Search API 智能竞品看板

用于长期跟踪 Tavily、Exa、Brave 等 AI Agent Search API 竞品动态，与 Querit 进展对照分析。

---

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动看板
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`。

---

## 项目结构

```
competitor_dashboard/
├── app.py                    # Streamlit 主入口，自动建表
├── config.py                 # 全局配置（路径、枚举值、字段映射）
├── database.py               # SQLite CRUD 封装
├── models.py                 # CompetitorUpdate dataclass
├── requirements.txt
├── README.md
├── services/
│   ├── excel_importer.py     # Excel 解析、字段校验、自动补全
│   ├── data_service.py       # 业务查询、批量写入、导出
│   └── archive_service.py    # 历史归档统计
├── pages/
│   ├── 1_本周看板.py          # 本周已确认动态与指标
│   ├── 2_数据导入.py          # Excel 上传与预览
│   ├── 3_待审核区.py          # 审核、编辑、确认/忽略
│   └── 4_历史动态.py          # 全量历史搜索与导出
├── templates/
│   └── competitor_updates_template.xlsx   # 填写模板
├── data/
│   └── competitor_dashboard.db            # 运行时自动生成
└── tests/
    ├── test_database.py
    ├── test_excel_importer.py
    └── test_data_service.py
```

---

## Excel 模板填写说明

模板位于 `templates/competitor_updates_template.xlsx`，也可在「数据导入」页面下载。

| 列名 | 是否必填 | 说明 |
|------|---------|------|
| 发布时间 | 建议填写 | 格式 `YYYY-MM-DD`，如 `2026-07-20` |
| 竞品 | 建议填写 | 下拉选择：`Tavily` / `Exa` / `Brave` / `Querit` / `Other` |
| 动态标题 | **必填** | 简洁描述该动态，如"Tavily 发布新版 Search API" |
| 动态概述 | 建议填写 | 100-200字描述动态内容要点 |
| 原始链接 | **必填** | 信息来源 URL，用于系统去重，相同 URL 不重复导入 |
| 信息平台 | 建议填写 | 下拉选择：`官网` / `Blog` / `GitHub` / `X` / `LinkedIn` / `Discord` / `Event` / `Other` |
| 备注 | 可选 | 可填写初步差距判断或注意事项 |

> 上传后系统自动补充：收录时间、来源模式（manual_excel）、周次（如 2026-W30）、默认审核状态（待审核）。

---

## 页面功能说明

### 本周看板
- 仅展示当前周、已确认的数据
- 顶部 7 个指标：新增动态数、各分类数量、高优先级数、Querit 覆盖数、最后更新时间
- 按「产品与功能 / 生态与集成 / 市场与运营」三个 tab 展示
- 支持按竞品、分类、优先级、Querit 状态筛选

### 数据导入
- 下载填写模板
- 上传 .xlsx 文件，自动解析并预览
- 校验必填字段和日期格式，逐行给出中文错误提示
- 确认后写入数据库，返回成功/重复/失败计数
- 相同 URL 自动跳过，不重复导入

### 待审核区
- 展示所有 review_status=待审核 的记录
- 可补充：分类、业务意义、Querit 状态、差距判断、建议动作、优先级
- 点击「标记已确认」→ 进入本周看板；点击「标记已忽略」→ 从待审核区移除
- 只有「已确认」的数据进入本周看板

### 历史动态
- 展示所有已确认的历史数据（跨周）
- 支持按时间范围、周次、竞品、分类、平台、Querit 状态、关键词筛选
- 支持导出当前筛选结果为 Excel

---

## 数据库字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 自增主键 |
| publish_date | TEXT | 信息发布时间 |
| collected_at | TEXT | 收录时间（系统自动填充） |
| competitor | TEXT | 竞品名称 |
| category | TEXT | 分类 |
| title | TEXT | 动态标题（必填）|
| summary | TEXT | 动态概述 |
| source_url | TEXT UNIQUE | 原始链接（必填，用于去重）|
| source_platform | TEXT | 信息平台 |
| source_mode | TEXT | 来源模式（manual_excel / querit_api）|
| business_value | TEXT | 业务意义 |
| querit_status | TEXT | Querit 对照状态 |
| gap_analysis | TEXT | 差距判断 |
| suggested_action | TEXT | 建议动作 |
| priority | TEXT | 优先级（高/中/低）|
| review_status | TEXT | 审核状态 |
| follow_up_status | TEXT | 跟进状态 |
| week_id | TEXT | ISO 周次（如 2026-W30）|
| updated_at | TEXT | 最后更新时间 |

---

## 运行测试

```bash
pytest tests/ -v
```

---

## 下一步：接入 Querit API

接入点位于 `services/data_service.py`：

```python
# 在此添加 fetch_querit_updates() 方法
# source_mode 设为 "querit_api"
# 字段补全逻辑复用 excel_importer.enrich_records()
```

在 `config.py` 中已预留配置项（从环境变量读取）：

```python
QUERIT_API_BASE_URL = os.environ.get("QUERIT_API_BASE_URL", "")
QUERIT_API_KEY = os.environ.get("QUERIT_API_KEY", "")
```

---

## 安全说明

- SQLite 文件位于 `data/competitor_dashboard.db`，不要提交到版本控制
- 所有数据库写入使用参数化语句，防止 SQL 注入
- 不要在代码中硬编码任何 API Key
