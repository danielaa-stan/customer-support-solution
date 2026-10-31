# 01. Ownership and collaboration rules

## Repository map

```
/contracts        shared; edited only through the procedure in README
/server           A: MCP server, mock backend, safety guard, audit, tests
/agent            B: agent loop, prompt, RAG tools, chat UI
/data             C: seed data, policies, cases (input for A and B)
/analytics        C: conversation analyzer, dashboard
/docs             C: presentation, video script
/runtime          NOT in git: transcripts/ (created at runtime); databases live in a Docker volume
```

## Who writes and reads what

| Artifact | Writer | Reader |
|----------|--------|--------|
| `contracts/schema.sql` | A (with everyone's agreement) | A, C |
| `data/seed/seed.json` | C | A (loads into the database) |
| `data/policies/*.md`, `data/cases.json` | C | B (indexes for RAG) |
| PostgreSQL `support` database (tables from `schema.sql`) | **A only** (`support_app`) | C: read only (`support_reader`; `audit_log`, `tickets`, etc.) |
| `runtime/transcripts/{session_id}.json` | B | C |
| PostgreSQL `analytics` database (star schema; `analysis` view) | Analytics service (`analytics_app`) | Dashboard |
| MCP tools | A | B |
| RAG tools (`search_policy`, `find_similar_cases`) | B | B (agent) |

Main rules:

1. **Only A writes to the `support` database**. B changes state only through MCP tools.
2. **C does not write to other owners' files or tables**. The analyzer writes only to the `analytics` database and reads support data through `support_reader`.
3. **Do not edit other owners' folders**. If a change is needed, ask the owner.
4. **Everyone works in their own branch** (`feat/server`, `feat/agent`, `feat/data-analytics`) and merges into `main` through small PRs.
5. Secrets belong only in `.env` (listed in `.gitignore`). The repository contains `.env.example` without values.
6. **Everything must be in English**: code comments, documentation, policies, seed data text, examples, prompts, user messages, agent responses, and UI text.

## Shared configuration (`.env.example`)

| Variable | Default value | Used by |
|----------|---------------|---------|
| `GEMINI_API_KEY` | none | B, C (analyzer) |
| `SUPPORT_DATABASE_URL` | PostgreSQL URL for `support_app` in database `support` | A |
| `SUPPORT_READONLY_DATABASE_URL` | PostgreSQL URL for `support_reader` in database `support` | C (read only) |
| `TRANSCRIPTS_DIR` | `runtime/transcripts` | B, C |
| `ANALYTICS_DATABASE_URL` | PostgreSQL URL for `analytics_app` in database `analytics` | C |
| `DEMO_NOW` | `2026-10-31T12:00:00Z` | A (fixed "current time" for deterministic demos) |

`DEMO_NOW` keeps the refund window (14 days) and seed dates from shifting depending on when the demo runs.

## How A and B connect

- MCP transport: **stdio**. B starts the server as a subprocess: `python -m server.mcp_server`.
- One chat session = one server run (or one server context). Session context details are in [03-mcp-tools.md](03-mcp-tools.md).

## Checkpoints

| Time | What must be ready |
|------|--------------------|
| 12:15 | Contracts agreed (FROZEN v1.0), seed schema, and the first 3 tools (`get_user_profile`, `get_payments`, `issue_refund`) |
| 13:30 | Agent completes 3 demo scenarios end to end |
| 15:00 | Dashboard ready |
| 15:45 | Code freeze, video recording |
| 17:00 | Submission deadline (presentation + code ZIP) |

## OPEN: questions to resolve together

1. Autonomy levels and limits (see [04-business-rules.md](04-business-rules.md)): whether the defaults are suitable.
2. Whether RAG stays in B's area (recommended) or moves to the MCP server.
3. Confirmation of risky actions: a two-step flow through `confirm_action` (proposed) or a UI button.
4. Ownership of the transcript format and `analysis` (proposed: B owns transcripts, C owns analysis).
5. Name and branding of the fictional product for the demo.
