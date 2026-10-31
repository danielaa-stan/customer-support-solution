# Contract changelog

## Unreleased
- Align the backend plan catalog and fallback seed with the Ukraine pricing contract;
  accept empty runtime-table arrays in generated seeds and reject supplied runtime history.
- Align the regular monthly catalog with the supplied Ukraine pricing: Individual 4.99 USD,
  Duo 6.49 USD, Family 7.99 USD, and Student 2.49 USD. Regenerate synthetic cases and customer
  seed records, and update the analytics plan dimension without rewriting recorded financial facts.
- Model analytics as conversation and tool-call fact tables with shared dimensions,
  a policy-citation bridge, and an `analysis` compatibility view.
- Replace SQLite with PostgreSQL 18 in Docker; use identity columns, timezone-aware timestamps,
  and decimal monetary values. Add separate support, support-reader, and analytics roles and connection URLs.
- Require English for all project content and translate the remaining examples.

## v0.1 (draft)
- Initial version: area ownership, data model, MCP tools, business rules,
  knowledge base format, transcript and analysis, demo scenarios.
