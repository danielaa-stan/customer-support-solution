# Contract changelog

## Unreleased
- Model analytics as conversation and tool-call fact tables with shared dimensions,
  a policy-citation bridge, and an `analysis` compatibility view.
- Replace SQLite with PostgreSQL 18 in Docker; use identity columns, timezone-aware timestamps,
  and decimal monetary values. Add separate support, support-reader, and analytics roles and connection URLs.
- Require English for all project content and translate the remaining examples.

## v0.1 (draft)
- Initial version: area ownership, data model, MCP tools, business rules,
  knowledge base format, transcript and analysis, demo scenarios.
