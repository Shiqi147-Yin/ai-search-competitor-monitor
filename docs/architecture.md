# System Architecture

## Overview

The AI Search Competitor Monitor is a monitoring dashboard designed to track
public updates across AI Search API competitors.

The system combines three information discovery paths:

1. Official-source monitoring
2. Search API-based discovery
3. Manual supplementation for sources that are difficult to access automatically

The goal is to reduce missed updates caused by relying only on keyword search,
while keeping the monitoring workflow structured and reviewable.

---

## High-Level Architecture

```mermaid
flowchart TD
    A[Competitor Configuration]

    A --> B[Official Source Monitoring]
    A --> C[Search API Discovery]
    A --> D[Manual Source Input]

    B --> E[Raw Updates]
    C --> E
    D --> E

    E --> F[Filtering]
    F --> G[Deduplication]
    G --> H[Update Classification]
    H --> I[Summary Generation]
    I --> J[Unified Dashboard]
