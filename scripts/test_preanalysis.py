import sys, io
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from services.content_analyzer import analyze_record

cases = [
    {
        "label": "Exa Agent Skills X 帖子",
        "competitor": "Exa",
        "source_platform": "X",
        "title": "Exa Agent Skills: Recruit, sell, and research with AI",
        "summary": "Exa launches installable Agent Skills for recruiting, sales, and research use cases.",
        "raw_content": "Today we're releasing a set of skills that we use internally at Exa across GTM, Recruiting, and Engineering. npx skills add exa-labs/agent-skills. Available as composio skills.",
        "fetch_status": "success",
        "fetch_error": "",
        "capability_change": 1,
        "integration_change": 0,
        "docs_changed": 0,
        "developer_experience_change": 0,
        "change_summary": "",
        "source_url": "https://x.com/ExaDevelopers/status/123",
    },
    {
        "label": "Exa × Cerebras X 帖子",
        "competitor": "Exa",
        "source_platform": "X",
        "title": "Exa × Cerebras: Fast inference meets neural search",
        "summary": "New Exa integration with Cerebras for ultra-fast inference combined with neural web search.",
        "raw_content": "Integration with Cerebras brings together Exa neural search and Cerebras high-speed inference platform for real-time agent workflows.",
        "fetch_status": "success",
        "fetch_error": "",
        "capability_change": 0,
        "integration_change": 1,
        "docs_changed": 0,
        "developer_experience_change": 0,
        "change_summary": "",
        "source_url": "https://x.com/ExaDevelopers/status/456",
    },
    {
        "label": "LinkedIn RAISE Summit (HTTP 451 无正文)",
        "competitor": "Exa",
        "source_platform": "LinkedIn",
        "title": "https://linkedin.com/posts/exa-ai_raise-summit-2026",
        "summary": "",
        "raw_content": "",
        "fetch_status": "restricted",
        "fetch_error": "HTTP 451",
        "capability_change": 0,
        "integration_change": 0,
        "docs_changed": 0,
        "developer_experience_change": 0,
        "change_summary": "",
        "source_url": "https://linkedin.com/posts/exa-ai_raise-summit-2026",
    },
]

for case in cases:
    label = case.pop("label")
    print(f"\n{'='*60}")
    print(f"[{label}]")
    result = analyze_record(case)
    print(f"  category:          {result.category}")
    print(f"  secondary_tags:    {result.secondary_tags}")
    print(f"  priority:          {result.priority}")
    print(f"  querit_status:     {result.querit_status}")
    print(f"  analysis_status:   {result.analysis_status}")
    print(f"  confidence:        {result.analysis_confidence:.0%}")
    print(f"  business_value:    {result.business_value[:80]}")
    print(f"  suggested_action:  {result.suggested_action[:60]}")
    print(f"  gap_analysis:      {result.gap_analysis[:60]}")
