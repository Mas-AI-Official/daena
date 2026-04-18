---
name: web-search
description: "Search the web for current information, news, documentation, and real-time data. Use when user asks about recent events, needs up-to-date info, or references something beyond training data."
department: Research
cost_tier: low
requires: {}
---

# Web Search Skill

Search the web to find current information when training data may be outdated.

## When to Use

- Questions about recent events, news, or current data
- Looking up documentation for specific library versions
- Finding real-time information (prices, weather, schedules)
- Verifying facts that may have changed since training cutoff

## How to Execute

Use available MCP tools or browser agent to search:

1. Formulate a clear, specific search query
2. Execute the search via available tools
3. Parse and summarize relevant results
4. Cite sources in the response

## Query Optimization

- Use specific terms, not vague phrases
- Include version numbers when searching for library docs
- Add the current year for time-sensitive queries
- Use site-specific searches when targeting known sources (e.g., "site:docs.python.org")
