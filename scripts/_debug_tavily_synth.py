"""Debug: check what Tavily mcp synthesizer outputs."""
import sys
sys.path.insert(0, '.')
from services.official_source_monitor import load_monitoring_config, run_official_monitor

result = run_official_monitor(
    competitor="Tavily",
    window_start="2026-07-08",
    window_end="2026-07-17",
    source_types=["all"],
    enable_querit_supplement=False,
)
print(f"github_results: {len(result.github_results)}")
for item in result.github_results:
    title = item.update_title or ""
    synth = getattr(item, 'synthesis_method', '?')
    print(f"  [{item.update_date}] {title[:80]} | synthesis={synth}")
    be = getattr(item, 'github_business_event', None)
    if be:
        print(f"    event_type={be.event_type} evidence={be.evidence_count}")
        for eid in be.evidence_record_ids[:3]:
            print(f"      eid={eid}")
