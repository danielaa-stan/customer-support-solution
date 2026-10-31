# server: support MCP server (zone A)

C# / .NET 10, the official MCP SDK (`ModelContextProtocol`), SQLite. Contract: [`../contracts`](../contracts).

## Run

```bash
dotnet build server/SupportServer.slnx
dotnet test  server/SupportServer.slnx

# MCP server (stdio). The agent (B) starts it using MCP_SERVER_COMMAND
dotnet run --project server/SupportServer -c Release

# clean database (deletes runtime/support.db and recreates it from the seed)
dotnet run --project server/SupportServer -c Release -- reset-db
```

Note for B: the project lives in `server/SupportServer`, so `MCP_SERVER_COMMAND` must be
`dotnet run --project server/SupportServer -c Release` (not `--project server`).
`dotnet run` may print build output to stdout, which would corrupt the MCP stream. The safest launch is to build once
(`dotnet build -c Release server/SupportServer.slnx`) and then start
`dotnet server/SupportServer/bin/Release/net10.0/SupportServer.dll`.

Environment variables (all optional):

| Variable | Default | Purpose |
|----------|---------|---------|
| `SUPPORT_DATABASE_URL` | none | PostgreSQL URL (`postgresql://support_app:password@localhost:5432/support`). When set, the server uses PostgreSQL |
| `SUPPORT_DB_PATH` | `runtime/support.db` | SQLite file, used only when `SUPPORT_DATABASE_URL` is not set |
| `SEED_PATH` | `data/seed/seed.json`, otherwise `server/dev-seed.json` | initial data |
| `DEMO_NOW` | `2026-10-31T12:00:00Z` | "current time" for deterministic demos (`real` = real clock) |
| `LOG_LEVEL` | `Information` | `Verbose`, `Debug`, `Information`, `Warning`, `Error` |
| `LOG_DIR` | `runtime/logs` | folder for file logs |
| `ALLOW_SESSION_SWITCH` | `false` | local development only: lets one process switch the user |

Relative paths are resolved from the repository root (the folder containing `contracts/`), so the working directory does not matter.

## Database: PostgreSQL or SQLite

The server reads the repository `.env` itself, so the agent does not have to forward any variables.

| Mode | When | Notes |
|------|------|-------|
| PostgreSQL | `SUPPORT_DATABASE_URL` is set | The real mode for the demo. Uses the shared schema `contracts/schema.sql` (created by Docker). |
| SQLite | `SUPPORT_DATABASE_URL` is not set | Local development and the unit tests; no Docker needed. Uses its own copy of the schema, `Infrastructure/Db/schema.sqlite.sql`. |

Start with PostgreSQL:

```powershell
Copy-Item .env.example .env          # set the four passwords, then use the same support password in SUPPORT_DATABASE_URL
docker compose up -d
dotnet run --project server/SupportServer -c Release -- reset-db   # wipes support data and loads the seed
dotnet run --project server/SupportServer -c Release
```

Notes:
- The server connects as `support_app` (the only role allowed to write). On start it creates the schema if it is missing and loads the seed when the `users` table is empty.
- `reset-db` truncates all support tables and loads the seed again; use it before recording the demo.
- If `contracts/schema.sql` changes, Docker only applies it to an empty volume: run `docker compose down -v` first. Keep `schema.sqlite.sql` in sync.
- The automated tests run on SQLite. The PostgreSQL path is checked manually (see the steps above and `docker/check-databases.sql`).
- Dates travel through the domain as ISO 8601 text. `SqlDialect` casts them to `TIMESTAMPTZ` on the way in and formats them back on the way out, so the tools and services are identical for both databases.

## Architecture

```
Tools  ->  ToolRunner  ->  Services  ->  Domain.Policies (guard)
 (MCP)     (context,        (use cases)   (pure rules)
           audit, format)        |
                                 v
                      Ports: IBillingProvider, IAuditLog
                                 ^
                      Infrastructure: MockBillingProvider, SqlAuditLog, SqlSupportStore (PostgreSQL or SQLite)
```

| Layer | Folder | Responsibility |
|-------|--------|----------------|
| Tools | `Tools/` | Thin MCP layer: tool description and a call to `ToolRunner`. No logic. |
| Application | `Application/` | `ToolRunner` (session context, audit, common response format), use-case services, ports. |
| Domain | `Domain/` | Models and **pure rules** (`RefundPolicy`, `DuplicateChargeDetector`): a safety guard with no dependencies, fully testable. |
| Infrastructure | `Infrastructure/` | PostgreSQL and SQLite access (`DbConnectionFactory`, `SqlDialect`), `MockBillingProvider`, `SqlAuditLog`, `SqlSupportStore`, seed loading. |
| Config | `Config/` | Business constants (`BusinessRules`) from `contracts/04-business-rules.md`. |

Key decisions:

1. **The guard lives outside the LLM.** Rules are plain code; the model cannot talk its way around them.
2. **User isolation.** `user_id` is set only by `sys_set_context` (called by B). The model never passes it and cannot act on another account.
3. **Auditing cannot be forgotten.** Every tool runs through `ToolRunner`, which writes `audit_log` for refusals as well.
4. **Billing is replaceable with one class.** `IBillingProvider` is a port; `MockBillingProvider` is one implementation.
5. **One schema.** `contracts/schema.sql` is embedded into the build, so the DB always matches the contract.
6. **Model claims are verified.** The `double_charge` reason of a refund is checked against the payment data.

## Logging

Two different kinds of logs that are deliberately kept apart:

| | Audit log | Diagnostic log |
|---|-----------|----------------|
| Audience | business, dashboard, judges | developer |
| Where | `audit_log` table in SQLite | `runtime/logs/server-YYYYMMDD.log` and stderr |
| Content | who did what and why (AI actions) | startup, calls, refusals, errors with stack traces |

Diagnostic logs use Serilog; the code itself only uses the standard `ILogger<T>`, and Serilog is wired in `Program.cs` only.
`stdout` is reserved for the MCP protocol, so the console sink writes to `stderr`. Files roll daily and 7 days are kept.

One tool call produces one line:

```
12:04:11 [WRN] issue_refund -> denied POLICY_DENIED refund-policy#2.1 | session=ses_01 user=u_demo_family | 3 ms, audit=128
```

Levels: Information (successful calls), Warning (policy refusals, `needs_human`, invalid arguments), Error (unhandled exceptions),
Debug (call arguments; enable with `LOG_LEVEL=Debug`). Logs contain identifiers only: no names, emails or keys.

## Session context protection

`sys_set_context` is called only by the system (B); the model must not see it. As defense in depth, after the first call the server
refuses to change the user or session, and `user_turn` can only grow. A new conversation means a new server process.
For local experiments with several users in one process use `ALLOW_SESSION_SWITCH=true`.

## Tool status

| Tool | Autonomy | State |
|------|----------|-------|
| `sys_set_context` | internal | done |
| `get_user_profile`, `get_payments`, `get_available_offers` | read | done |
| `issue_refund`, `pause_subscription`, `change_plan`, `apply_retention_offer`, `escalate_to_human`, `reject_action` | auto | done |
| `cancel_subscription` + `confirm_action` | confirm | done (two-step flow) |

All 12 tools from `contracts/03-mcp-tools.md` are implemented, with tests for demo scenarios 1, 2, 3 and the bonus escalation.

### Two-step confirmation

`cancel_subscription` only records a `pending_actions` row and returns `pending_confirmation`. `confirm_action` executes it, but only when
`user_turn` is greater than the turn of the proposal, i.e. after a NEW customer message. Pending actions are bound to the session and user,
repeating the same proposal returns the same pending action, and a rejected or confirmed action cannot be confirmed again.

## How to add a tool

1. The rule (if any) goes into `Domain/Policies/` with a test.
2. A method in a service that returns `ToolOutcome` (`Done`, `Denied`, `HumanRequired`, `Fail`).
3. A thin method in `Tools/` with `[McpServerTool]` that calls `runner.Run(...)`.
4. A test in `SupportServer.Tests/ToolFlowTests.cs`.
