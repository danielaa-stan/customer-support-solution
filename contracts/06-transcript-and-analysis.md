# 06. Транскрипт розмови та результат аналізу

## Спільні enum

`intent` (основний намір):
`cancel_subscription`, `billing_issue`, `refund_request`, `plan_change`, `technical_issue`, `account_access`, `other`

`reason_code` (справжня причина; використовують і інструменти A, і аналізатор C):
`price_too_high`, `low_usage`, `technical_problems`, `switching_competitor`, `double_charge`,
`billing_confusion`, `temporary_break`, `other`, `unknown`

`resolution` (результат розмови):
`resolved_auto` (AI вирішив сам), `retained` (клієнта утримано), `canceled`, `refunded`, `escalated`, `abandoned`

## Транскрипт: `runtime/transcripts/{session_id}.json` (пише B, читає C)

B записує файл, коли розмова завершилась (користувач пішов, проблему вирішено, ескалація). Також дозволено перезаписувати файл під час розмови.

```json
{
  "session_id": "ses_20261031_0001",
  "user_id": "u_demo_family",
  "started_at": "2026-10-31T12:00:05Z",
  "ended_at": "2026-10-31T12:04:41Z",
  "end_reason": "resolved_by_agent",
  "messages": [
    {"seq": 1, "role": "user", "ts": "2026-10-31T12:00:05Z",
     "content": "Дуже дорого стало, хочу скасувати підписку."},
    {"seq": 2, "role": "assistant", "ts": "2026-10-31T12:00:09Z",
     "content": "Розумію. Дозвольте подивитися ваш акаунт ...",
     "tool_calls": [{"name": "get_user_profile", "args": {}}]},
    {"seq": 3, "role": "tool", "ts": "2026-10-31T12:00:10Z",
     "name": "get_user_profile", "content": {"ok": true, "status": "done"}}
  ]
}
```

Правила:

- `role`: `user` | `assistant` | `tool` | `system`.
- `end_reason`: `resolved_by_agent` | `escalated` | `user_left`.
- `seq` починається з 1 і зростає. `content` повідомлень `tool` містить фактичну відповідь інструмента (можна скорочувати великі поля).
- Виконані дії C бере **не з транскрипта, а з `audit_log`** (джерело правди про виконане). Транскрипт потрібен для тексту розмови.

## Результат аналізу: таблиця `analysis` у `runtime/analytics.db` (власник C)

Один рядок на сесію. B і A цю таблицю не використовують.

| Поле | Тип | Опис |
|------|-----|------|
| `session_id` | TEXT PK | |
| `user_id` | TEXT | |
| `primary_intent` | TEXT | enum `intent` |
| `underlying_reason` | TEXT | enum `reason_code` (справжня причина, може відрізнятися від сказаного) |
| `sentiment_start` | INTEGER | −2 (дуже негативний) … +2 (дуже позитивний) |
| `sentiment_end` | INTEGER | те саме |
| `churn_risk` | REAL | 0.0 – 1.0 після розмови |
| `resolution` | TEXT | enum `resolution` |
| `actions_json` | TEXT | список виконаних дій (береться з `audit_log`) |
| `policy_refs_json` | TEXT | використані політики |
| `quality_json` | TEXT | оцінка якості відповіді AI: `{"correctness":1-5,"policy_compliance":1-5,"tone":1-5,"resolved":true}` |
| `kb_gap` | INTEGER | 1, якщо агент не знайшов відповіді в базі знань |
| `summary` | TEXT | 1–2 речення для дашборду |
| `analyzed_at` | TEXT | ISO 8601 |

## Що показує дашборд (мінімум)

1. Топ причин скасування (`underlying_reason`).
2. Частка розмов, вирішених AI самостійно, проти ескальованих.
3. Скільки клієнтів утримано і яка пропозиція спрацювала.
4. Кількість і сума автоматичних refund.
5. Середня якість відповідей AI та прогалини в базі знань (`kb_gap`).
6. Журнал дій AI (з `audit_log`) для вибраної розмови.
