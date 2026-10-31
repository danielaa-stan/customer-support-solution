# 07. Demo scenarios

C generates seed data for these scenarios, B configures the agent, and A checks the rules.
The identifiers and amounts below are **fixed**: tests and the video depend on them.
"Current" time: `DEMO_NOW = 2026-10-31T12:00:00Z`.

## Scenario 1. "Too expensive": retention through a shared plan

**User:** `u_demo_family`, Olena, `individual` plan (4.99 USD), tenure ≈ 8.7 months (since 2026-02-10),
`listening_hours_30d = 41.5`, `devices_count = 2`, no previous retention offers.

**Message:** "It has become too expensive for me. I want to cancel my subscription."

**Expected agent behavior:**
1. `get_user_profile`, `get_available_offers`, `search_policy("reducing costs, shared plan")`.
2. Sees high activity → underlying reason is `price_too_high`, not `low_usage`.
3. Offers **one** alternative: shared `family` plan (6 seats, 7.99 USD, ≈ 1.33 USD per person with 6 members) and/or `discount_50_3m`.
4. Customer chooses the discount → `apply_retention_offer(discount_50_3m)` (`retention-rules#1.1`).

**Expected result:** `subscription.discount_percent = 50`, `discount_payments_left = 3`, a row in `retention_offers_used`.
Analysis: `primary_intent = cancel_subscription`, `underlying_reason = price_too_high`, `resolution = retained`.

## Scenario 2. Duplicate charge: automatic refund

**User:** `u_demo_double`, `individual` plan, active.

**Payments:**
- `pay_demo_dbl_1`: 4.99 USD, `renewal`, `succeeded`, `2026-10-29T08:00:00Z`
- `pay_demo_dbl_2`: 4.99 USD, `renewal`, `succeeded`, `2026-10-29T08:02:00Z`

**Message:** "I was charged twice for my subscription! Please refund my money."

**Expected behavior:**
1. `get_payments` → `duplicate_charge_candidates` contains the pair.
2. `search_policy("duplicate charge")`.
3. `issue_refund(payment_id="pay_demo_dbl_2", reason_code="double_charge", policy_ref="refund-policy#2.2")`: 4.99 ≤ 20, within the 14-day window, executed automatically.
4. The agent explains the decision with a policy reference.

**Expected result:** `pay_demo_dbl_2.status = refunded`; repeating `issue_refund` with the same `payment_id` returns `ALREADY_DONE`.
Analysis: `primary_intent = refund_request`, `underlying_reason = double_charge`, `resolution = refunded`.

## Scenario 3. "Just cancel": fair cancellation without pressure

**User:** `u_demo_cancel`, `individual` plan (4.99 USD), tenure ≈ 14 months, `listening_hours_30d = 1.2`,
`last_active_at = 2026-09-20T18:00:00Z`.

**Dialogue:**
1. User: "Just cancel my subscription."
2. Agent: checks the situation (profile), offers **one** alternative: a 3-month pause (`low_usage`).
3. User: "No, cancel it."
4. Agent: `cancel_subscription(reason_code="low_usage", effective="end_of_period")` → `pending_confirmation`; explains the consequences (access until the next billing date) and requests confirmation.
5. User: "Yes." → `confirm_action(pending_action_id)`.

**Expected result:** `status = active` with `cancel_at = next_billing_date`, no further charges. The agent **does not** offer a discount a second time (`cancellation#1.1`).
Analysis: `primary_intent = cancel_subscription`, `underlying_reason = low_usage`, `resolution = canceled`, high `churn_risk`.

## Bonus (time permitting): escalation of a large refund (copilot)

**User:** `u_demo_escalate`, payment `pay_demo_big`: 23.97 USD, `other`, `succeeded`, `2026-10-27T10:00:00Z` (accidental charge for 3 months in advance).

**Expected behavior:** `issue_refund` → `LIMIT_EXCEEDED` (`refund-policy#2.3`, `needs_human = true`) →
`escalate_to_human(priority="high", category="refund_request", summary=..., suggested_action={tool:"issue_refund", args:{...}, rationale, policy_ref})`.
The dashboard shows a ticket with a prepared recommendation for the human agent.

## Who checks what

| Check | Owner |
|-----------|-----|
| seed data contains all demo users with exact IDs, amounts, and dates | C |
| tool responses match expectations (automated tests for each scenario) | A |
| agent completes scenarios end to end and cites `policy_ref` | B |
| analysis produces the expected `underlying_reason` and `resolution` | C |
