# 02. Data model and seed data

Source of truth: [schema.sql](schema.sql). This document provides explanations and the seed file format.

Storage: PostgreSQL 18, started through the root `compose.yaml`. JSON field names remain unchanged.
Dates are ISO 8601 UTC strings in JSON and `TIMESTAMPTZ` in PostgreSQL. Monetary amounts use
`NUMERIC(10,2)` in PostgreSQL. Keep `is_student` as integer `0` or `1` in seed data.
Fields ending in `_json` remain JSON-encoded text; callers serialize and parse them explicitly.

## Entities

| Table | Purpose | Who changes state |
|---------|-------------|-----------------|
| `users` | customer profile | seed |
| `subscriptions` | plan, status, discounts, next billing date | MCP tools |
| `payments` | charge and refund history | seed + `issue_refund` |
| `usage_stats` | listening over 30 days, devices | seed |
| `retention_offers_used` | retention offers already applied | `apply_retention_offer` |
| `tickets` | escalations to a human agent | `escalate_to_human` |
| `pending_actions` | actions awaiting confirmation | `confirm`-level tools |
| `audit_log` | every tool call | server automatically |

## Enum values

- `plan`: `individual`, `duo`, `family`, `student`
- `subscription.status`: `active`, `paused`, `canceled`, `past_due`
- `payment.status`: `succeeded`, `failed`, `refunded`
- `payment.kind`: `renewal`, `plan_change`, `other`
- `ticket.priority`: `low`, `normal`, `high`, `urgent`
- `autonomy_level`: `read`, `auto`, `confirm`, `human_only`
- `result_status`: `done`, `pending_confirmation`, `denied`, `needs_human`, `error`
- `reason_code`, `intent`: see [06-transcript-and-analysis.md](06-transcript-and-analysis.md)

## Seed file: `data/seed/seed.json` (written by C, loaded by A)

Structure: an object whose keys match table names and whose values are arrays of table rows
with exactly the same field names as in `schema.sql`.

```json
{
  "users": [
    {"id": "u_demo_family", "name": "Olena Koval", "email": "olena@example.com",
     "country": "UA", "is_student": 0, "created_at": "2026-02-10T09:00:00Z"}
  ],
  "subscriptions": [
    {"id": "sub_demo_family", "user_id": "u_demo_family", "plan": "individual",
     "pending_plan": null, "status": "active", "price_amount": 9.99, "price_currency": "USD",
     "started_at": "2026-02-10T09:00:00Z", "next_billing_date": "2026-11-10T09:00:00Z",
     "paused_until": null, "cancel_at": null, "discount_percent": 0, "discount_payments_left": 0}
  ],
  "payments": [
    {"id": "pay_0001", "user_id": "u_demo_family", "amount": 9.99, "currency": "USD",
     "kind": "renewal", "status": "succeeded", "charged_at": "2026-10-10T09:00:00Z",
     "refunded_at": null, "refund_reason": null}
  ],
  "usage_stats": [
    {"user_id": "u_demo_family", "listening_hours_30d": 41.5,
     "last_active_at": "2026-10-30T20:10:00Z", "devices_count": 2, "offline_downloads": 120}
  ],
  "retention_offers_used": []
}
```

Seed data rules:

1. All dates are relative to `DEMO_NOW = 2026-10-31T12:00:00Z`.
2. The three demo users from [07-demo-scenarios.md](07-demo-scenarios.md) with fixed IDs are required.
3. Additionally, 30–50 "background" users with various plans, statuses, and payment histories.
4. `tickets`, `pending_actions`, and `audit_log` are empty in the seed data (populated during system operation).
5. A writes `server/seed_loader.py`, which validates the seed data against the schema and fails with a clear error.
