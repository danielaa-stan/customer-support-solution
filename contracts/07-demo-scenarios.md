# 07. Демо-сценарії

Під ці сценарії C генерує seed, B налаштовує агента, A перевіряє правила.
Ідентифікатори й суми нижче **фіксовані**: на них спираються тести та відео.
Час «зараз»: `DEMO_NOW = 2026-10-31T12:00:00Z`.

## Сценарій 1. «Дорого»: утримання через спільний план

**Користувач:** `u_demo_family`, Олена, план `individual` (9.99 USD), стаж ≈ 8,7 міс (з 2026-02-10),
`listening_hours_30d = 41.5`, `devices_count = 2`, пропозицій утримання раніше не було.

**Повідомлення:** «Для мене стало дорого, хочу скасувати підписку.»

**Очікувана поведінка агента:**
1. `get_user_profile`, `get_available_offers`, `search_policy("зниження вартості, спільний план")`.
2. Бачить високу активність → справжня причина `price_too_high`, а не `low_usage`.
3. Пропонує **одну** альтернативу: спільний план `family` (6 місць, 15.99 USD, ≈ 2.67 USD з людини при 6 учасниках) і/або `discount_50_3m`.
4. Клієнт обирає знижку → `apply_retention_offer(discount_50_3m)` (`retention-rules#1.1`).

**Очікуваний результат:** `subscription.discount_percent = 50`, `discount_payments_left = 3`, рядок у `retention_offers_used`.
Аналіз: `primary_intent = cancel_subscription`, `underlying_reason = price_too_high`, `resolution = retained`.

## Сценарій 2. Подвійне списання: автоматичний refund

**Користувач:** `u_demo_double`, план `individual`, активний.

**Платежі:**
- `pay_demo_dbl_1`: 9.99 USD, `renewal`, `succeeded`, `2026-10-29T08:00:00Z`
- `pay_demo_dbl_2`: 9.99 USD, `renewal`, `succeeded`, `2026-10-29T08:02:00Z`

**Повідомлення:** «Мене двічі списали за підписку! Поверніть гроші.»

**Очікувана поведінка:**
1. `get_payments` → `duplicate_charge_candidates` містить пару.
2. `search_policy("подвійне списання")`.
3. `issue_refund(payment_id="pay_demo_dbl_2", reason_code="double_charge", policy_ref="refund-policy#2.2")`: 9.99 ≤ 20, у вікні 14 днів, виконується автоматично.
4. Агент пояснює рішення з посиланням на політику.

**Очікуваний результат:** `pay_demo_dbl_2.status = refunded`; повторний `issue_refund` тим самим `payment_id` дає `ALREADY_DONE`.
Аналіз: `primary_intent = refund_request`, `underlying_reason = double_charge`, `resolution = refunded`.

## Сценарій 3. «Просто скасуйте»: чесне скасування без тиску

**Користувач:** `u_demo_cancel`, план `individual` (9.99 USD), стаж ≈ 14 міс, `listening_hours_30d = 1.2`,
`last_active_at = 2026-09-20T18:00:00Z`.

**Діалог:**
1. Користувач: «Просто скасуйте мою підписку.»
2. Агент: з'ясовує ситуацію (профіль), пропонує **одну** альтернативу: пауза 3 місяці (`low_usage`).
3. Користувач: «Ні, скасуйте.»
4. Агент: `cancel_subscription(reason_code="low_usage", effective="end_of_period")` → `pending_confirmation`; переказує наслідки (доступ до дати наступного списання), просить підтвердження.
5. Користувач: «Так.» → `confirm_action(pending_action_id)`.

**Очікуваний результат:** `status = active` з `cancel_at = next_billing_date`, нових списань немає. Агент **не** пропонує знижку вдруге (`cancellation#1.1`).
Аналіз: `primary_intent = cancel_subscription`, `underlying_reason = low_usage`, `resolution = canceled`, високий `churn_risk`.

## Бонус (за часом): ескалація великого refund (copilot)

**Користувач:** `u_demo_escalate`, платіж `pay_demo_big`: 47.97 USD, `other`, `succeeded`, `2026-10-27T10:00:00Z` (випадкове списання за 3 місяці наперед).

**Очікувана поведінка:** `issue_refund` → `LIMIT_EXCEEDED` (`refund-policy#2.3`, `needs_human = true`) →
`escalate_to_human(priority="high", category="refund_request", summary=..., suggested_action={tool:"issue_refund", args:{...}, rationale, policy_ref})`.
Дашборд показує тікет із готовою рекомендацією для агента-людини.

## Хто що перевіряє

| Перевірка | Хто |
|-----------|-----|
| seed містить усіх демо-користувачів із точними ID, сумами й датами | C |
| відповіді інструментів збігаються з очікуваними (автотести на кожен сценарій) | A |
| агент проходить сценарії end-to-end і цитує `policy_ref` | B |
| аналіз видає очікувані `underlying_reason` і `resolution` | C |
