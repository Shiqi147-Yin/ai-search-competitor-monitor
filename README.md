# AI Search Competitor Monitor

A competitor monitoring dashboard for tracking public updates across AI Search API products.

The system combines official-source crawling, Search API-based discovery, manual URL input for restricted sources, and a review workflow to support recurring competitor research.

## Monitored Competitors

The project was primarily tested with:

- Tavily
- Exa
- Brave Search

## Monitoring Sources

The monitoring workflow covers public sources including:

- Official websites
- Blogs
- Documentation
- Changelogs
- GitHub
- X
- LinkedIn
- Discord
- Event and partner pages

Different sources are handled differently depending on their accessibility and page structure.

## Core Workflow

```text
Competitor / Source / Time Window
                ↓
        Information Discovery
       ↙        ↓         ↘
Official      Search API     Manual URL
Sources       Discovery      Supplement
       ↘        ↓         ↙
          Result Processing
                ↓
     Freshness / Relevance Check
                ↓
        Deduplication & Review
                ↓
          Confirmed Updates
                ↓
        Weekly Dashboard / History
```

## Key Capabilities

- Competitor-specific source configuration
- Source-targeted English query generation
- Time-window based retrieval
- Official entry-page detection
- Blog and documentation drill-down
- GitHub repository and commit retrieval
- Search API supplementary discovery
- Manual URL import for restricted sources
- Freshness checks
- Source authority and relevance classification
- URL deduplication
- Review before final dashboard entry
- Weekly dashboard and historical record views

## Official-Source Monitoring

For structured official sources, the system can identify entry pages and drill down into individual updates.

Examples include:

- Blog index → individual blog posts
- Documentation index → updated documentation pages
- GitHub repository → commits or releases

Results are evaluated against the selected monitoring time window before entering the review workflow.

## Search API Discovery

Search API retrieval is used as an additional discovery path.

Queries are generated separately for source types such as:

- Official Blog
- Documentation
- GitHub
- Events
- Social announcements

Queries include competitor-specific source constraints and explicit date ranges.

## Manual Supplementation

Some social and community platforms cannot be fetched reliably through the automated pipeline.

For sources such as X, LinkedIn, and Discord, public URLs can be added manually and processed through the same downstream workflow.

## Review Workflow

Retrieved records are not treated as confirmed competitor updates immediately.

The system supports:

- Freshness validation
- Source authority checks
- Competitor relevance classification
- Duplicate detection
- Manual review
- Confirmation before dashboard entry

## Validation

The project includes automated tests for major components such as:

- Database operations
- URL deduplication
- GitHub parsing and analysis
- Restricted-source handling
- Excel / URL import
- Dashboard filtering
- Review workflow
- Source-targeted query generation

## Repository Scope

This repository is a sanitized reconstruction for portfolio purposes.

It does not contain proprietary code, credentials, internal infrastructure, confidential business data, or non-public information from previous employers.
