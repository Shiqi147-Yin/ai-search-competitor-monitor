# 产品设计：从信息发现到人工确认

本文根据本仓库中的原始应用代码整理。它描述已实现的本地原型，不宣称已完成线上生产部署或真实服务效果评估。

## 目标与使用流程

面向 AI Search API 竞品研究，将 Tavily、Exa、Brave 等来源的公开动态整理成可审核记录，并让用户填写 Querit 对照状态、业务意义、差距与后续动作。

1. 在“数据导入”输入单条或批量 URL，或导入 Excel；也可使用“Querit 智能检索”和“官方来源巡检”。
2. 预览结果、识别重复记录、检查时间与来源证据，然后由用户选择入库。
3. 在“待审核区”查看自动建议并补充人工判断，确认或忽略记录。
4. 在“本周看板”查看当前周次的已确认记录；在“历史动态”跨周筛选并导出。

## 关键设计与代码依据

| 设计 | 实现依据 | 实际边界 |
| --- | --- | --- |
| 多入口发现 | `pages/2_数据导入.py`、`pages/6_Querit智能检索.py`、`pages/7_官方来源巡检.py` | 三条入口使用不同处理管线，并非每条都经过相同检查 |
| 入口页下钻 | `services/source_drilldown.py`、`services/website_monitor.py` | 依赖页面结构和网络，不保证所有站点成功 |
| GitHub 结构化监测 | `services/github_monitor.py`、`services/github_fetcher.py` | 对提交和发布等进行采集；不代表具备所有 GitHub 对象的完整语义分析 |
| 文档更新识别 | `services/docs_change_detector.py`、`services/docs_snapshot_store.py` | 首次发现不等于新发布；缺失可靠日期时需要人工判断 |
| 受限来源降级 | `services/url_fetcher.py`、`services/source_capability_classifier.py` | X、LinkedIn 等可保留 URL 并标记受限，不代表绕过访问限制 |
| 可解释建议 | `services/content_analyzer.py`、`services/classification_rules.py` | 关键词规则和模板，不是已接入大模型的通用理解能力 |
| 人工审核 | `services/data_service.py`、`pages/3_待审核区.py` | 确认是用户操作，不是事实真实性的自动保证 |
| 周次视图 | `services/data_service.py:get_weekly_dashboard` | 按 `week_id` 与 `review_status=已确认` 查询，不单纯按原文发布日期判断 |

## 数据质量处理

URL 标准化、重复检测、来源权威性、竞品相关性和日期判断分别在相关服务中实现。不同导入路径的检查范围不同：手工 Excel 数据不能被描述为已经自动完成所有来源核验。

`services/freshness_filter.py` 区分窗口内、窗口外、缺失日期、无效日期和未来日期。官方文档巡检还参考快照与有效来源日期。仅仅“今天首次采集到”不能证明页面本期发生了更新。

自动分析根据抓取成功程度和内容完整度限制置信度；已有人工分析字段在重抓取时受到保护。最终商业判断由用户补充。

## 评测与未完成能力

仓库提供基准配置、匹配器与诊断脚本，用于比较结果与预期事件。本次核验运行了 774 项自动化测试，未实测真实 Querit 凭据，也未给出实时召回率、准确率或全站覆盖率。

GitHub 事件合成默认走 Mock provider。OpenAI 和 Anthropic provider 的 `synthesize` 方法抛出 `NotImplementedError`，因此不将真实模型驱动的事件合成列为已完成能力。

## 运行范围

当前应用为 Streamlit + SQLite 本地原型，没有多用户身份认证、角色权限或应用内定时调度服务。官方来源巡检由界面或命令行触发。公开仓库不携带原有运行数据库与密钥。
