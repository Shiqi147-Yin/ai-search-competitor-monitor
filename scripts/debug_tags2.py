import sys; sys.path.insert(0,'.')
combined = "we're releasing a set of skills that we use internally at exa npx skills add exa-labs/agent-skills"
print("'agent skills' in combined:", 'agent skills' in combined)
print("'npx skills' in combined:", 'npx skills' in combined)
print("'skills add' in combined:", 'skills add' in combined)
print("'exa-labs/agent-skills' in combined:", 'exa-labs/agent-skills' in combined)

from services.classification_rules import SECONDARY_TAG_HINTS
for tag, hints in SECONDARY_TAG_HINTS.items():
    matched = [h for h in hints if h in combined]
    if matched:
        print(f"TAG: {tag} <- {matched}")
