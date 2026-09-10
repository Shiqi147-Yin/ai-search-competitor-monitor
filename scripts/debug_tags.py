import sys; sys.path.insert(0,'.')
from services.content_analyzer import analyze_record
rec = {
    'competitor':'Exa','source_platform':'X',
    'title':"We're releasing a set of skills that we use internally at Exa",
    'summary':'npx skills add exa-labs/agent-skills',
    'raw_content':"We use these skills across GTM. npx skills add exa-labs/agent-skills",
    'capability_change':0,'integration_change':0,'docs_changed':0,
    'developer_experience_change':0,'change_summary':'','fetch_status':'success',
}
r = analyze_record(rec)
combined = (rec['title']+' '+rec['summary']+' '+rec['raw_content']).lower()
from services.classification_rules import SECONDARY_TAG_HINTS
for tag, hints in SECONDARY_TAG_HINTS.items():
    matched = [h for h in hints if h in combined]
    if matched:
        print(f"TAG HIT: {tag} <- {matched}")
print("secondary_tags:", r.secondary_tags)
