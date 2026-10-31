# 03. Інструменти MCP (контракт A ↔ B)

Реалізує A (`/server`), викликає B (`/agent`). Транспорт: stdio, бібліотека FastMCP (Python).

## Контекст сесії (безпека)

LLM **ніколи** не передає `user_id` і не обирає, чий акаунт змінювати. Сервер працює лише над користувачем поточної сесії.

Для цього є службовий інструмент із префіксом `sys_`. **B не показує `sys_*` інструменти моделі.**

| Інструмент | Параметри | Коли викликає B |
|------------|-----------|-----------------|
| `sys_set_context` | `session_id: str`, `user_id: str`, `user_turn: int` | на початку чату і перед кожною реплікою користувача (`user_turn` = лічильник повідомлень користувача, з 1) |

Усі інструменти нижче без `sys_set_context` повертають `error.code = "NO_CONTEXT"`.

## Єдиний формат відповіді

Кожен інструмент повертає JSON такого вигляду:

```json
{
  "ok": true,
  "status": "done",
  "data": { },
  "error": null,
  "needs_human": false,
  "audit_id": 128
}
```

| Поле | Опис |
|------|------|
| `ok` | `true`, якщо дію виконано або запропоновано; `false` у разі відмови чи помилки |
| `status` | `done` · `pending_confirmation` · `denied` · `needs_human` · `error` |
| `data` | результат (залежить від інструмента) або `null` |
| `error` | `null` або `{ "code": "...", "message": "...", "policy_ref": "refund-policy#2.1" }` |
| `needs_human` | `true`, якщо агент має передати кейс людині (`escalate_to_human`) |
| `audit_id` | id запису в `audit_log` |

`error.message` написано так, щоб агент міг переказати причину клієнту. `policy_ref` (якщо є) агент цитує.

### Коди помилок

| Код | Значення |
|-----|----------|
| `NO_CONTEXT` | не викликано `sys_set_context` |
| `NOT_FOUND` | об'єкт не існує або належить іншому користувачу |
| `INVALID_ARGUMENT` | неправильні параметри |
| `POLICY_DENIED` | політика забороняє (див. `policy_ref`) |
| `NOT_ELIGIBLE` | пропозиція недоступна цьому користувачу |
| `ALREADY_DONE` | дію вже виконано (ідемпотентність) |
| `LIMIT_EXCEEDED` | перевищено ліміт автоматичної дії → `needs_human = true` |
| `CONFIRMATION_REQUIRED` | потрібне підтвердження користувача |
| `CONFIRMATION_INVALID` | підтвердження неможливе (нема нового повідомлення користувача, прострочено) |
| `INTERNAL` | непередбачена помилка |

## Рівні автономності

| Рівень | Поведінка |
|--------|-----------|
| `read` | лише читання, без побічних ефектів |
| `auto` | виконується одразу, якщо правила дозволяють |
| `confirm` | сервер створює `pending_action` і повертає `pending_confirmation`; виконується після `confirm_action` |
| `human_only` | сервер відмовляє з `needs_human = true`; далі `escalate_to_human` |

**Двокроковий потік `confirm`:**

1. Агент викликає, напр., `cancel_subscription(...)`. Відповідь: `status = pending_confirmation`, `data.pending_action_id`, `data.summary`.
2. Агент переказує клієнту, що саме станеться, і просить явне підтвердження.
3. Клієнт відповідає. B збільшує `user_turn` і викликає `sys_set_context`.
4. Агент викликає `confirm_action(pending_action_id)`. Сервер виконує дію лише якщо `user_turn` **більший** за `proposed_at_turn` (тобто після пропозиції було нове повідомлення користувача). Інакше `CONFIRMATION_INVALID`.
5. Якщо клієнт відмовився: `reject_action(pending_action_id)`.

## Інструменти, видимі моделі

### Читання (`read`)

**`get_user_profile()`** → `data`:
```json
{
  "user": {"id": "u_...", "name": "...", "country": "UA", "is_student": false},
  "subscription": {"plan": "individual", "status": "active", "price_amount": 9.99,
                   "price_currency": "USD", "next_billing_date": "...", "tenure_months": 8,
                   "pending_plan": null, "paused_until": null, "cancel_at": null,
                   "discount_percent": 0},
  "usage": {"listening_hours_30d": 41.5, "last_active_at": "...", "devices_count": 2},
  "flags": {"retention_offer_used_in_cooldown": false}
}
```

**`get_payments(limit: int = 10)`** → `data.payments`: масив `{id, amount, currency, kind, status, charged_at, refunded_at, refund_reason}`, від нових до старих. Додатково `data.duplicate_charge_candidates`: масив пар `payment_id`, які виглядають як подвійне списання (див. правила в 04).

**`get_available_offers()`** → `data.offers`: масив `{code, title, description, details}` лише тих пропозицій, на які користувач **зараз має право** (сервер сам перевіряє). Агент не вигадує пропозиції.

### Дії

**`pause_subscription(months: int, reason_code: str)`** · `auto`
- `months` від 1 до `PAUSE_MAX_MONTHS`. Плата не стягується під час паузи.
- `data`: `{paused_until}`.

**`change_plan(new_plan: str, reason_code: str)`** · `auto`
- `new_plan`: `individual` | `duo` | `family` | `student` (`student` лише якщо `is_student`).
- Підвищення плану діє одразу, зниження з наступного списання (`pending_plan`).
- `data`: `{plan, pending_plan, effective, new_price_amount}`.

**`apply_retention_offer(offer_code: str, reason_code: str)`** · `auto`
- `offer_code` має бути з `get_available_offers()`. Інакше `NOT_ELIGIBLE`.
- `data`: `{offer_code, discount_percent, discount_payments_left}` або `{free_months}`.

**`issue_refund(payment_id: str, reason_code: str, policy_ref: str)`** · `auto` / `human_only` залежно від правил
- Умови й ліміти: [04-business-rules.md](04-business-rules.md).
- Успіх: `data`: `{payment_id, refunded_amount, currency}`.
- Платіж поза вікном: `POLICY_DENIED` (`refund-policy#2.1`).
- Сума понад автоматичний ліміт: `LIMIT_EXCEEDED`, `needs_human = true`.
- Повторний виклик для вже повернутого платежу: `ALREADY_DONE`.

**`cancel_subscription(reason_code: str, effective: str = "end_of_period")`** · `confirm`
- `effective`: `end_of_period` (за замовчуванням) або `immediate`.
- Відповідь: `pending_confirmation`. Після `confirm_action`: `data`: `{status, cancel_at}`.

**`confirm_action(pending_action_id: str)`** · виконує підтверджену дію (результат такий, як у відповідного інструмента).

**`reject_action(pending_action_id: str)`** · скасовує очікувану дію.

**`escalate_to_human(priority: str, category: str, summary: str, suggested_action: object | null)`** · `auto`
- Створює тікет для агента-людини. `summary`: коротке зведення проблеми й що вже зроблено. `suggested_action`: `{tool, args, rationale, policy_ref}` або `null` (це «copilot-рекомендація» для людини).
- `data`: `{ticket_id}`.

## Інструменти зони B (не MCP): для довідки

Реєструє B поруч з MCP-інструментами. Модель бачить їх так само.

- `search_policy(query: str, top_k: int = 3)` → масив `{doc_id, section, title, text, policy_ref}`
- `find_similar_cases(query: str, top_k: int = 3)` → масив `{case_id, title, resolution, actions, outcome, policy_refs}`

## Audit log: що пише сервер автоматично

Для **кожного** виклику (також для відмов): `ts`, `session_id`, `user_id`, `tool`, `args`, `result_status`,
`error_code`, `autonomy_level`, `reason_code`, `policy_ref`, `actor`.
`confirm_action` додає окремий запис і зберігає зв'язок через `args`.

## Ідемпотентність

Повторний виклик дії, яка вже виконана (той самий `payment_id`, той самий стан підписки), не виконує її вдруге,
а повертає `ALREADY_DONE` без побічних ефектів.
