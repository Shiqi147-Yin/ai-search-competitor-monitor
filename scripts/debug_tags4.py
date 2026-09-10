import sys; sys.path.insert(0,'.')
from services.classification_rules import SECONDARY_TAG_HINTS
combined = "we're releasing a set of skills that we use internally at exa npx skills add exa-labs/agent-skills we use these skills across gtm. npx skills add exa-labs/agent-skills  "

print("Agent Skills hints:", SECONDARY_TAG_HINTS.get("Agent Skills"))
for h in SECONDARY_TAG_HINTS.get("Agent Skills", []):
    print(f"  '{h}' in combined:", h in combined)
