# Product Design

## Background

The project was built to support recurring competitor research for AI Search API products.

The monitoring scope included competitors such as Tavily, Exa, and Brave Search, with updates distributed across official websites, documentation, GitHub, social platforms, and other public channels.

---

## Core Problem

A single retrieval method could not reliably cover all monitored sources.

During actual monitoring, different sources showed different access and discovery characteristics.

For example:

- Official blogs contain structured product announcements.
- Documentation pages may change without appearing as normal news articles.
- GitHub updates are represented through repositories, commits, releases, pull requests, or documentation changes.
- X, LinkedIn, and Discord have stronger automated-access limitations.

The monitoring workflow therefore needed different handling strategies for different source types.

---

## Product Approach

The final monitoring mechanism separates discovery into three paths.

### Official-source monitoring

Structured official sources are actively checked.

The system recognizes entry pages and drills down into specific updates rather than treating an index page as an update itself.

### Search API discovery

Search API retrieval provides additional discovery coverage.

Instead of using one broad query, queries are split by source type and constrained by competitor and time window.

### Manual URL supplementation

Restricted channels are retained in the workflow through manual URL input.

This allows publicly available social or community updates to be analyzed together with automatically discovered records.

---

## Source-specific Design

### Blog

Blog index pages are treated as entry pages.

The system drills down to individual articles and checks whether their publication dates fall inside the monitoring window.

### Documentation

Documentation entry pages can be expanded into individual documentation pages.

Update timestamps can be obtained from available page or sitemap metadata.

### GitHub

GitHub repositories are treated as structured technical sources.

The system distinguishes different GitHub object types such as:

- Repository
- Commit
- Release
- Pull request
- Issue
- Documentation-related pages

GitHub changes can also be classified by update type.

### Restricted Social Sources

For sources where stable automatic fetching is not available, the system retains the URL and marks the record for manual handling rather than discarding it.

---

## Time-window Control

Competitor research is performed within a defined monitoring period.

Search queries use explicit start and end dates.

Official-source results are also evaluated against the same monitoring window.

This prevents older content from being mixed directly into the current monitoring batch.

---

## Quality Control

The workflow contains several checks before an update becomes a confirmed record.

### Source Authority

Results are evaluated based on whether they come from:

- Official sources
- Ecosystem or partner sources
- Third-party sources
- Unknown sources
- Low-value aggregators

### Relevance

Results are evaluated against the target competitor and known monitoring targets.

### Freshness

Published or updated dates are compared against the selected monitoring window.

### Duplicate Detection

Normalized URLs are checked against existing records before import.

### Manual Review

Records can be reviewed before being confirmed into the dashboard.

---

## Benchmark Validation

A benchmark set of manually identified competitor events was used during development to evaluate retrieval recall.

The benchmark workflow compares discovered results with expected events using information such as:

- Exact URL
- Domain
- Keywords
- Event title

This benchmark was used to test and improve the retrieval workflow rather than being part of the final competitor dashboard itself.

---

## Human + Automated Workflow

The project does not assume that every information source can be fully automated.

Instead, the working model is:

```text
Automated Monitoring
        +
Manual Supplementation
        ↓
Shared Processing
        ↓
Manual Review
        ↓
Confirmed Dashboard Records
```

Official websites, blogs, documentation, changelogs, and GitHub are the main targets for automated processing.

Restricted social and community sources can be supplemented manually.

---

## Output

Confirmed records are used for recurring competitor monitoring and weekly review.

The system also retains historical confirmed records for later reference.

---

## Repository Scope

This document only describes product decisions supported by the reconstructed project.

It excludes confidential strategy, internal business data, proprietary infrastructure, and non-public information.
