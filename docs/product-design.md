# Product Design

## Background

Competitor intelligence for AI Search APIs requires continuous tracking across multiple public channels.

Important updates may appear on:

- Official websites
- Product blogs
- Changelogs
- Documentation
- GitHub
- Social media
- Community channels
- Partnership or event pages

Relying on a single retrieval method makes it difficult to maintain both coverage and efficiency.

---

## Problem Definition

The initial monitoring approach relied heavily on keyword-based retrieval.

During testing, several limitations became clear:

### 1. Incomplete coverage

Some important updates were not reliably discovered through generic keyword search, especially when they were published on specific official pages or repositories.

### 2. Different source characteristics

Information sources behave differently.

Official websites, documentation pages, GitHub repositories, and social platforms have different structures, update patterns, and accessibility constraints.

A single retrieval strategy could not handle all sources equally well.

### 3. Duplicate and noisy results

Search-based discovery could return repeated, outdated, or irrelevant content, increasing manual review cost.

### 4. Fragmented review workflow

Updates discovered from different channels had to be reviewed separately, making weekly competitor tracking inefficient.

---

## Design Goal

The redesigned monitoring dashboard focused on four goals:

- Improve update discovery coverage
- Prioritize high-confidence official sources
- Reduce duplicate and irrelevant results
- Centralize updates into a unified review workflow

---

## Solution

The final workflow combines three complementary discovery methods:

### 1. Official Source Monitoring

Official sources are treated as the primary monitoring path.

Typical sources include:

- Official websites
- Blogs
- Changelogs
- Documentation
- GitHub repositories

The purpose is to directly monitor channels where product and technical updates are most likely to appear.

### 2. Search API Discovery

Search API retrieval is used as a supplementary discovery layer.

It helps identify public updates that may not be included in the predefined official-source list.

Queries can be adjusted by:

- Competitor
- Source type
- Monitoring category
- Date range
- Monitoring objective

### 3. Manual Supplementation

Some sources are difficult to monitor reliably through automated methods.

For these channels, relevant public URLs can be manually added into the workflow.

This keeps human review as part of the system rather than treating manual work as an exception outside the dashboard.

---

## Processing Workflow

After discovery, results enter a shared processing workflow:

```text
Discovery
    ↓
Relevance Filtering
    ↓
Date Validation
    ↓
Deduplication
    ↓
Category Assignment
    ↓
Summary
    ↓
Unified Dashboard
```

This allows results from different discovery methods to be reviewed using the same structure.

---

## Information Structure

Competitor updates are organized by dimensions such as:

- Product updates
- API and documentation changes
- GitHub activity
- Ecosystem integrations
- Partnerships
- Events
- Use cases
- Benchmarks

This structure supports both single-competitor tracking and cross-competitor comparison.

---

## Product Iteration

The monitoring workflow was iterated based on actual retrieval performance.

### Early Approach

```text
Keyword-based Search
        ↓
Manual Review
```

This approach was simple, but coverage depended heavily on query quality and search indexing.

### Intermediate Exploration

Different query strategies and source-specific retrieval methods were tested to improve discovery quality.

However, relying primarily on search still created coverage gaps for important official updates.

### Final Approach

```text
Official Source Monitoring
        +
Search API Discovery
        +
Manual Supplementation
        ↓
Unified Processing
        ↓
Dashboard
```

The final design separates information discovery into multiple paths based on source characteristics, then brings the results back into a shared analysis and review workflow.

---

## Key Product Decisions

### Official sources first

Official channels are prioritized because they provide higher-confidence information and clearer update ownership.

### Search as supplementation, not the only entry point

Search API retrieval improves coverage but is not treated as the sole monitoring method.

### Human-in-the-loop by design

Manual supplementation is retained for sources that are difficult to automate reliably.

Instead of attempting full automation, the system focuses on reducing repetitive work while preserving necessary human judgment.

### Unified downstream processing

Regardless of how an update is discovered, it enters the same filtering, classification, and review workflow.

This reduces fragmentation across monitoring channels.

---

## Outcome

The redesigned workflow established a more structured competitor monitoring process across multiple AI Search API competitors.

It enabled:

- More systematic official-source tracking
- Supplementary discovery through Search APIs
- Structured handling of manually added sources
- Unified classification and review
- Weekly competitor update aggregation

The project also provided a reusable framework for evaluating which parts of competitive intelligence monitoring should be automated and where human review remains necessary.

---

## Repository Scope

This document describes a sanitized reconstruction of the product design process.

It does not include confidential business strategies, internal data, proprietary infrastructure, credentials, or non-public information from previous employers.
