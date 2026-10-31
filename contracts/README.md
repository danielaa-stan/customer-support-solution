# Team contracts: AI Customer Support (music streaming)

Status: **DRAFT v0.1**. Once all three team members agree, change to **FROZEN v1.0**.

This folder is the single shared location for A, B, and C. It describes **what** we exchange
(tables, tools, file formats). Each area owner decides **how** to implement it within their area.

## Who is who

| Area | Role | Folders |
|------|------|---------|
| A | Backend / MCP: mock backend, MCP server, safety guard, audit log, tests | `/server` |
| B | AI agent + RAG + chat UI | `/agent` |
| C | Data, policies, conversation analyzer, dashboard, presentation | `/data`, `/analytics`, `/docs` |

## Reading order

1. [01-ownership.md](01-ownership.md): responsibilities, rules to avoid overlap, checkpoints
2. [02-data-model.md](02-data-model.md) + [schema.sql](schema.sql): tables and seed data format
3. [03-mcp-tools.md](03-mcp-tools.md): MCP tools, response format, errors, autonomy levels
4. [04-business-rules.md](04-business-rules.md): single source of truth for numbers and rules (limits, windows, offers)
5. [05-knowledge-base-format.md](05-knowledge-base-format.md): policies and similar cases for RAG
6. [06-transcript-and-analysis.md](06-transcript-and-analysis.md): conversation and analysis result formats
7. [07-demo-scenarios.md](07-demo-scenarios.md): three demo scenarios for which we generate data

## Contract change procedure

1. To change a contract, describe exactly what and why in the group chat.
2. After agreement, one of the three makes the changes in the `contracts` branch and adds an entry to [CHANGELOG.md](CHANGELOG.md).
3. The others pull the changes (`git pull`) before using them.
4. After the 13:30 checkpoint, contracts may be changed only as a last resort.

## Open questions (team decision needed)

Marked `OPEN` in the documents. A short list is at the end of [01-ownership.md](01-ownership.md).
