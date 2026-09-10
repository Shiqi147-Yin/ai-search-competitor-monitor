import sys; sys.path.insert(0,'.')
from services.content_analyzer import analyze_record
from services.classification_rules import SECONDARY_TAG_HINTS

rec = {
    'competitor':'Exa','source_platform':'X',
    'title':"We're releasing a set of skills that we use internally at Exa",
    'summary':'npx skills add exa-labs/agent-skills',
    'raw_content':"We use these skills across GTM. npx skills add exa-labs/agent-skills",
    'capability_change':0,'integration_change':0,'docs_changed':0,
    'developer_experience_change':0,'change_summary':'','fetch_status':'success',
}

title = rec['title']
summary = rec['summary']
raw_content = rec['raw_content']
combined = " ".join([title, summary, raw_content[:1000], '', '', '']) .lower()

print("combined sample:", combined[:150])
print()
for tag, hints in SECONDARY_TAG_HINTS.items():
    matched = [h for h in hints if h in combined]
    if matched:
        print(f"MATCHED TAG: {tag} <- {matched}")

print()
r = analyze_record(rec)
print("secondary_tags:", r.secondary_tags)
