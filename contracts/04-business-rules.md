# 04. Business rules: single source of truth

All three team members use these values:
A implements them in the safety guard, C includes them in policies (`data/policies`), B cites them in responses.
**If a number changes, it changes here and in all three places.**

## Constants

| Constant | Value |
|-----------|----------|
| `REFUND_WINDOW_DAYS` | 14 (from the charge date) |
| `AUTO_REFUND_LIMIT` | 20.00 USD (above this: human only) |
| `PAUSE_MAX_MONTHS` | 3 |
| `RETENTION_COOLDOWN_MONTHS` | 12 (one retention offer per 12 months) |
| `DUPLICATE_CHARGE_WINDOW_HOURS` | 24 |
| `DEMO_NOW` | 2026-10-31T12:00:00Z |

## Plans

| Plan | Price (USD/month) | Seats | Note |
|------|----------------|-------|----------|
| `individual` | 9.99 | 1 | |
| `duo` | 12.99 | 2 | |
| `family` | 15.99 | 6 | |
| `student` | 4.99 | 1 | only if `is_student = 1` |

## Retention offers

| Code | Benefit | Eligibility conditions |
|-----|--------|-------------|
| `discount_50_3m` | 50% discount on the next 3 charges | status `active`, tenure ≥ 3 months, plan is not `student`, no offers within `RETENTION_COOLDOWN_MONTHS` |
| `free_month_1` | 1 free month | status `active`, tenure ≥ 12 months, no offers within `RETENTION_COOLDOWN_MONTHS` |

Switching to a cheaper or shared plan (`duo`, `family`, `student`) **is not** a retention offer; it is a regular `change_plan`.
The agent may recommend it based on the price per person (Family with 6 seats).

## Refunds

- Allowed if the payment is `succeeded`, has not been refunded, and ≤ `REFUND_WINDOW_DAYS` have elapsed since `charged_at`.
- Amount ≤ `AUTO_REFUND_LIMIT`: executed automatically (`auto`).
- Amount > `AUTO_REFUND_LIMIT`: `LIMIT_EXCEEDED` → agent escalates (`human_only`).
- Duplicate charge: two `succeeded` payments of the same amount by the same user, ≤ `DUPLICATE_CHARGE_WINDOW_HOURS` apart. Refund the second payment with reason `double_charge`.

## Cancellation

- Default: `end_of_period`; access remains until `next_billing_date`, with no further charges.
- `immediate` does not automatically grant a refund; refunds follow the refund rules.
- Cancellation always requires explicit user confirmation (`confirm`).
- **Ethical policy (no dark patterns):** the agent may offer an alternative **once** after identifying the reason.
  If the user repeats their wish to cancel, the agent cancels without further persuasion.

## Pause

- 1–`PAUSE_MAX_MONTHS` months, with no charges. The subscription automatically resumes after `paused_until`.

## Policies in `data/policies` (required documents and anchors)

Numbering must match this table because the server and demo scenarios reference it.

| doc_id | Required sections |
|--------|--------------------|
| `refund-policy` | `2.1` 14-day window · `2.2` duplicate charge · `2.3` automatic limit and escalation |
| `retention-rules` | `1.1` offer eligibility · `1.2` 12-month cooldown · `1.3` one offer per conversation |
| `cancellation` | `1.1` right to cancel and "one alternative" · `1.2` cancellation at the end of the period |
| `plans-and-pricing` | `1.1` prices and seats · `1.2` student plan eligibility · `1.3` plan changes |
| `pause-policy` | `1.1` pause for up to 3 months |
| `known-issues` | `1.x` common bugs (offline, CarPlay, lost playlists, login error) |
| `escalation-matrix` | `1.1` when to hand over to a human · `1.2` priorities |
| `agent-conduct` | `1.1` tone · `1.2` ban on dark patterns · `1.3` do not invent rules |
