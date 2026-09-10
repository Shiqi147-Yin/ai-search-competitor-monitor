"""分类关键词规则库（纯规则，不依赖 LLM）"""

# ── 一级分类关键词 ──────────────────────────────────────────────

CATEGORY_KEYWORDS = {
    "产品与功能": [
        "api", "pricing", "search mode", "streaming", "research", "deep search",
        "mcp", "oauth", "sdk", "timeout", "performance", "reliability",
        "product update", "place search", "agent skills", "quota", "feature release",
        "new feature", "release", "launch", "rate limit", "endpoint", "parameter",
        "authentication", "token", "cost", "latency", "accuracy", "recall",
        "search quality", "real-time", "realtime", "web search", "neural search",
        "keyless", "key-less", "rerank", "crawl", "extract", "llm", "rag",
        # 新增 Agent Skills 高优先级关键词
        "skills add", "install skill", "reusable skills", "company research",
        "lead generation", "people search", "candidate sourcing", "build with",
        "recruiting", "engineering workflow", "we're releasing", "we are releasing",
        "npx skills", "installable", "set of skills", "use internally",
    ],
    "生态与集成": [
        "integration", "connector", "plugin", "skill integration", "mcp server",
        "coding agent", "ai ide", "langchain", "llamaindex", "crewai",
        "mastra", "kiro", "nvidia", "cerebras", "n8n", "flowise", "dify",
        "partner ecosystem", "ecosystem", "framework", "agent framework",
        "openai", "anthropic", "gemini", "cursor", "copilot", "vscode",
        "jupyter", "zapier", "make.com", "composio", "haystack", "autogen",
        "instructor", "pydantic", "open source", "github action",
        "hugging face", "together ai", "groq", "mistral", "cohere",
        "vercel", "together", "ollama",
    ],
    "市场与运营": [
        "event", "summit", "webinar", "hackathon", "developer meetup",
        "partnership announcement", "product positioning", "blog campaign",
        "community", "customer story", "social campaign", "conference",
        "sponsorship", "announcement", "press release", "funding", "series",
        "investor", "valuation", "growth", "traction", "testimonial",
        "case study", "marketing", "brand", "awareness", "outreach",
        "user story", "promotion", "discount", "free tier", "trial",
        "raise summit", "dev cup", "hackathon", "developer event",
        "launch event",
    ],
}

# ── Agent Skills 强关键词（出现即强制归为产品与功能）─────────────
STRONG_PRODUCT_SIGNALS = [
    "agent skills",
    "skills add",
    "npx skills",
    "install skill",
    "reusable skills",
    "use internally",
    "we're releasing",
    "new api",
    "api release",
]

STRONG_ECOSYSTEM_SIGNALS = [
    "cerebras",
    "kiro",
    "nvidia integration",
    "llamaindex",
    "langchain",
    "vercel integration",
    "composio",
]

STRONG_MARKET_SIGNALS = [
    "summit",
    "hackathon",
    "raise summit",
    "dev cup",
    "sponsoring",
]

# 每个分类的 secondary_tags 提取关键词
SECONDARY_TAG_HINTS = {
    "Agent Skills": ["agent skills", "agent skill", "skills marketplace",
                     "skills add", "npx skills", "install skill", "reusable skills",
                     "use internally", "exa-labs/agent-skills", "agent-skills"],
    "生态分发": ["ecosystem", "distribution", "marketplace", "app store",
                "composio", "build with"],
    "开发者工具": ["npx", "developer tools", "sdk", "cli",
                  "engineering workflow"],
    "MCP": ["mcp", "model context protocol"],
    "Cerebras": ["cerebras"],
    "模型平台": ["model platform", "inference", "groq", "cerebras", "together", "nvidia"],
    "LangChain": ["langchain"],
    "LlamaIndex": ["llamaindex", "llama index"],
    "定价变化": ["pricing", "price", "cost", "free tier", "quota", "rate limit", "cheaper"],
    "Streaming": ["streaming", "stream"],
    "合作": ["partnership", "partner", "collaboration", "alliance"],
    "活动": ["event", "summit", "webinar", "hackathon", "conference", "meetup"],
    "Kiro": ["kiro"],
    "开源": ["open source", "opensource", "github"],
    "Coding Agent": ["coding agent", "ai ide", "cursor", "copilot", "vscode", "kiro"],
    "Place Search": ["place search", "poi", "local search"],
    "Vercel": ["vercel"],
}

# ── 优先级判断 ──────────────────────────────────────────────────

HIGH_PRIORITY_KEYWORDS = [
    "new api", "api launch", "api release", "pricing", "rate limit",
    "major release", "streaming", "mcp", "oauth", "coding agent", "kiro",
    "cerebras", "nvidia", "deep search", "research mode", "agent skills",
    "place search", "llm integration", "product launch", "feature release",
    "breaking change", "skills add", "npx skills",
]

LOW_PRIORITY_KEYWORDS = [
    "blog post", "blog campaign", "social", "tweet", "linkedin post",
    "typo", "readme fix", "minor", "documentation fix", "small update",
    "community post", "light", "formatting",
]

# ── business_value 生成模板 ─────────────────────────────────────

BUSINESS_VALUE_TEMPLATES = {
    ("产品与功能", "agent skills"): (
        "将搜索能力封装为可直接安装的业务场景，降低开发者接入门槛，"
        "并扩大竞品在销售、招聘和研究类 Agent 中的分发。"
    ),
    ("产品与功能", "skills add"): (
        "将搜索能力封装为可直接安装的业务场景，降低开发者接入门槛，"
        "并扩大竞品在销售、招聘和研究类 Agent 中的分发。"
    ),
    ("产品与功能", "streaming"): (
        "实时流式返回搜索结果，支持更低延迟的 Agent 工作流，"
        "增强在高频实时场景下的竞争优势。"
    ),
    ("产品与功能", "pricing"): (
        "定价策略调整直接影响竞品市场定位与开发者采用成本，"
        "需评估对 Querit 定价策略的参考价值。"
    ),
    ("产品与功能", "mcp"): (
        "MCP 协议支持使竞品能够被主流 AI IDE 和 Agent 框架原生调用，"
        "显著提升生态覆盖和开发者使用便捷性。"
    ),
    ("产品与功能", "place search"): (
        "本地 POI 搜索能力扩展了 Search API 的使用场景，"
        "进一步覆盖地点发现、商户信息等高价值垂直需求。"
    ),
    ("生态与集成", "cerebras"): (
        "将实时搜索与高速推理平台结合，有利于提升低延迟 Agent 工作流的整体体验，"
        "并扩大竞品的模型平台合作范围。"
    ),
    ("生态与集成", "langchain"): (
        "进入 LangChain 生态意味着可被大量 Agent 开发者直接调用，"
        "快速扩大竞品的使用规模和社区影响力。"
    ),
    ("生态与集成", "kiro"): (
        "接入 Kiro 等 Coding Agent 工具，打通 AI 辅助编程场景中的搜索需求，"
        "拓展开发者侧的使用入口。"
    ),
    ("市场与运营", None): (
        "通过活动或内容传播提升品牌认知度和开发者社区影响力，"
        "可能影响竞品在开发者市场的心智份额。"
    ),
}

# ── suggested_action 模板 ──────────────────────────────────────

SUGGESTED_ACTION_TEMPLATES = {
    ("产品与功能", "agent skills"): (
        "评估 Querit 是否需要补充同类 Agent Skills 场景，并对比安装和调用体验。"
    ),
    ("产品与功能", "skills add"): (
        "评估 Querit 是否需要补充同类 Agent Skills 场景，并对比安装和调用体验。"
    ),
    ("产品与功能", "pricing"): (
        "对比竞品最新定价与 Querit 当前价格区间，评估是否需要调整定价策略。"
    ),
    ("产品与功能", "streaming"): (
        "评估 Querit 是否具备流式搜索能力，对比产品体验与延迟表现。"
    ),
    ("产品与功能", "mcp"): (
        "跟进 MCP 协议集成进展，评估 Querit 是否具备同类原生支持。"
    ),
    ("产品与功能", None): (
        "评估竞品新增能力对 Querit 的影响，对比产品体验并记录差距。"
    ),
    ("生态与集成", "kiro"): (
        "跟进 Kiro 等 Coding Agent 生态入口，评估是否具备接入价值。"
    ),
    ("生态与集成", "cerebras"): (
        "跟进 Cerebras 等模型平台合作方式，评估是否存在类似集成机会。"
    ),
    ("生态与集成", None): (
        "跟进该生态集成进展，评估 Querit 是否需要优先对接同类框架。"
    ),
    ("市场与运营", None): (
        "该内容以活动传播为主，暂不进入产品跟进，保留观察。"
    ),
    ("待评估", None): (
        "内容不足，需人工补充标题、摘要或正文后重新分析。"
    ),
}

# ── gap_analysis 模板 ─────────────────────────────────────────

GAP_ANALYSIS_TEMPLATES = {
    "agent skills": (
        "竞品已将搜索能力封装为可安装 Skill，Querit 是否具备同类场景覆盖和安装体验仍需人工确认。"
    ),
    "skills add": (
        "竞品已将搜索能力封装为可安装 Skill，Querit 是否具备同类场景覆盖和安装体验仍需人工确认。"
    ),
    "coding agent": (
        "该集成拓展了 Coding Agent 分发入口，Querit 当前对应接入情况待核实。"
    ),
    "mcp": (
        "MCP 支持已成为主流 AI 工具集成标准，Querit 当前对 MCP 的支持程度待确认。"
    ),
    "streaming": (
        "流式搜索能力已在竞品中出现，Querit 是否具备同类能力待人工确认。"
    ),
    "pricing": (
        "竞品定价策略有变化，需与 Querit 当前定价对比并人工评估影响。"
    ),
    "integration": (
        "竞品生态覆盖面持续扩大，Querit 在该方向的接入情况待人工核实。"
    ),
    "cerebras": (
        "该集成拓展了模型平台分发入口，Querit 当前是否存在同类接入仍待核实。"
    ),
    None: (
        "与 Querit 的差距评估需结合当前产品进展，请人工确认后填写。"
    ),
}

# ── 一级分类关键词 ──────────────────────────────────────────────

CATEGORY_KEYWORDS = {
    "产品与功能": [
        "api", "pricing", "search mode", "streaming", "research", "deep search",
        "mcp", "oauth", "sdk", "timeout", "performance", "reliability",
        "product update", "place search", "agent skills", "quota", "feature release",
        "new feature", "release", "launch", "rate limit", "endpoint", "parameter",
        "authentication", "token", "cost", "latency", "accuracy", "recall",
        "search quality", "real-time", "realtime", "web search", "neural search",
        "keyless", "key-less", "rerank", "crawl", "extract", "llm", "rag",
    ],
    "生态与集成": [
        "integration", "connector", "plugin", "skill", "mcp server",
        "coding agent", "ai ide", "langchain", "llamaindex", "crewai",
        "mastra", "kiro", "nvidia", "cerebras", "n8n", "flowise", "dify",
        "partner ecosystem", "ecosystem", "framework", "agent framework",
        "openai", "anthropic", "gemini", "cursor", "copilot", "vscode",
        "jupyter", "zapier", "make.com", "composio", "haystack", "autogen",
        "instructor", "pydantic", "open source", "github action",
        "hugging face", "together ai", "groq", "mistral", "cohere",
    ],
    "市场与运营": [
        "event", "summit", "webinar", "hackathon", "developer meetup",
        "partnership announcement", "product positioning", "blog campaign",
        "community", "customer story", "social campaign", "conference",
        "sponsorship", "announcement", "press release", "funding", "series",
        "investor", "valuation", "growth", "traction", "testimonial",
        "case study", "marketing", "brand", "awareness", "outreach",
        "user story", "promotion", "discount", "free tier", "trial",
    ],
}

# 每个分类的 secondary_tags 提取关键词（第一个定义删除，统一使用此处）
_SECONDARY_TAG_HINTS_PLACEHOLDER = None  # merged below

# ── business_value 生成模板 ─────────────────────────────────────

# key = (category, 场景关键词 or None)
BUSINESS_VALUE_TEMPLATES = {
    ("产品与功能", "agent skills"): (
        "将底层搜索能力包装为可直接安装的业务场景，降低开发者接入门槛，"
        "并扩大竞品在垂直类 Agent 中的分发覆盖。"
    ),
    ("产品与功能", "streaming"): (
        "实时流式返回搜索结果，支持更低延迟的 Agent 工作流，"
        "增强在高频实时场景下的竞争优势。"
    ),
    ("产品与功能", "pricing"): (
        "定价策略调整直接影响竞品市场定位与开发者采用成本，"
        "需评估对 Querit 定价策略的参考价值。"
    ),
    ("产品与功能", "mcp"): (
        "MCP 协议支持使竞品能够被主流 AI IDE 和 Agent 框架原生调用，"
        "显著提升生态覆盖和开发者使用便捷性。"
    ),
    ("产品与功能", "place search"): (
        "本地 POI 搜索能力扩展了 Search API 的使用场景，"
        "进一步覆盖地点发现、商户信息等高价值垂直需求。"
    ),
    ("生态与集成", "cerebras"): (
        "将搜索能力与高速推理平台结合，增强实时搜索与低延迟推理组合，"
        "对高频 Agent 工作流具有较强吸引力。"
    ),
    ("生态与集成", "langchain"): (
        "进入 LangChain 生态意味着可被大量 Agent 开发者直接调用，"
        "快速扩大竞品的使用规模和社区影响力。"
    ),
    ("生态与集成", "kiro"): (
        "接入 Kiro 等 Coding Agent 工具，打通 AI 辅助编程场景中的搜索需求，"
        "拓展开发者侧的使用入口。"
    ),
    ("市场与运营", None): (
        "通过活动或内容传播提升品牌认知度和开发者社区影响力，"
        "可能影响竞品在开发者市场的心智份额。"
    ),
}

# ── suggested_action 模板 ──────────────────────────────────────

SUGGESTED_ACTION_TEMPLATES = {
    ("产品与功能", "agent skills"): (
        "评估 Querit 是否需要补充同类 Agent Skills 场景，并对比安装与调用体验。"
    ),
    ("产品与功能", "pricing"): (
        "对比竞品最新定价与 Querit 当前价格区间，评估是否需要调整定价策略。"
    ),
    ("产品与功能", "streaming"): (
        "评估 Querit 是否具备流式搜索能力，对比产品体验与延迟表现。"
    ),
    ("产品与功能", "mcp"): (
        "跟进 MCP 协议集成进展，评估 Querit 是否具备同类原生支持。"
    ),
    ("产品与功能", None): (
        "评估竞品新增能力对 Querit 的影响，对比产品体验并记录差距。"
    ),
    ("生态与集成", "kiro"): (
        "跟进 Kiro 等 Coding Agent 生态入口，评估是否具备接入价值。"
    ),
    ("生态与集成", "cerebras"): (
        "关注搜索与推理平台集成趋势，评估 Querit 是否有类似合作机会。"
    ),
    ("生态与集成", None): (
        "跟进该生态集成进展，评估 Querit 是否需要优先对接同类框架。"
    ),
    ("市场与运营", None): (
        "当前主要为活动传播，保留观察，关注后续产品动态。"
    ),
    ("待评估", None): (
        "内容不足，需人工补充标题、摘要或正文后重新分析。"
    ),
}

# ── gap_analysis 模板 ─────────────────────────────────────────

GAP_ANALYSIS_TEMPLATES = {
    "agent skills": (
        "竞品已将搜索能力封装为可安装 Skill，Querit 是否具备同类场景覆盖仍需人工确认。"
    ),
    "coding agent": (
        "该集成拓展了 Coding Agent 分发入口，Querit 当前对应接入情况待核实。"
    ),
    "mcp": (
        "MCP 支持已成为主流 AI 工具集成标准，Querit 当前对 MCP 的支持程度待确认。"
    ),
    "streaming": (
        "流式搜索能力已在竞品中出现，Querit 是否具备同类能力待人工确认。"
    ),
    "pricing": (
        "竞品定价策略有变化，需与 Querit 当前定价对比并人工评估影响。"
    ),
    "integration": (
        "竞品生态覆盖面持续扩大，Querit 在该方向的接入情况待人工核实。"
    ),
    None: (
        "与 Querit 的差距评估需结合当前产品进展，请人工确认后填写。"
    ),
}
