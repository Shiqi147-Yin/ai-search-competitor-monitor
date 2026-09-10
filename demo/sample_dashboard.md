# Sample Dashboard Output

This file demonstrates a sanitized example of the type of confirmed competitor records managed by the monitoring dashboard.

It is not a reproduction of the original internal interface.

---

## Weekly View

**Monitoring Window:** 2026-08-08 to 2026-08-14

**Competitors:** Tavily, Exa, Brave Search

| Competitor | Date | Source | Category | Title | URL |
|---|---|---|---|---|---|
| Example A | 2026-08-10 | Official Blog | Product | Example product update | https://example.com/a |
| Example B | 2026-08-11 | GitHub | Ecosystem | Example integration update | https://example.com/b |
| Example C | 2026-08-12 | Documentation | Documentation | Example documentation update | https://example.com/c |

---

## Record Lifecycle

```text
Discovered / Imported
        ↓
Processed
        ↓
Reviewed
        ↓
Confirmed
        ↓
Weekly Dashboard
        ↓
History
```

Only reviewed and confirmed records are represented in the final dashboard output.

---

## Discovery Metadata

A monitoring record may retain information related to its discovery and processing, including:

```json
{
  "competitor": "Example A",
  "source_url": "https://example.com/update",
  "source_platform": "Blog",
  "published_at": "2026-08-10",
  "freshness_status": "within_window",
  "official_source": true,
  "review_status": "confirmed"
}
```

The fields above are illustrative representations of the types of metadata used in the monitoring workflow.

---

## Source Handling

```text
Official Blog / Docs / GitHub
            ↓
     Automated Processing

Search API Results
            ↓
     Automated Processing

X / LinkedIn / Restricted Sources
            ↓
       Manual URL Input
            ↓

        Shared Review
            ↓
     Confirmed Dashboard
```

---

## Notes

This demo intentionally uses sample records rather than real internal monitoring data.

The original project includes weekly dashboard and historical record views, but the interface and confidential business data are not reproduced here.
