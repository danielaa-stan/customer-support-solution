# 02. Модель даних і seed

Джерело правди: [schema.sql](schema.sql). Тут пояснення та формат seed-файлу.

## Сутності

| Таблиця | Призначення | Хто змінює стан |
|---------|-------------|-----------------|
| `users` | профіль клієнта | seed |
| `subscriptions` | план, статус, знижки, дата наступного списання | інструменти MCP |
| `payments` | історія списань і повернень | seed + `issue_refund` |
| `usage_stats` | прослуховування за 30 днів, пристрої | seed |
| `retention_offers_used` | які пропозиції утримання вже застосовано | `apply_retention_offer` |
| `tickets` | ескалації для агента-людини | `escalate_to_human` |
| `pending_actions` | дії, що чекають підтвердження | інструменти рівня `confirm` |
| `audit_log` | кожен виклик інструмента | сервер автоматично |

## Enum-значення

- `plan`: `individual`, `duo`, `family`, `student`
- `subscription.status`: `active`, `paused`, `canceled`, `past_due`
- `payment.status`: `succeeded`, `failed`, `refunded`
- `payment.kind`: `renewal`, `plan_change`, `other`
- `ticket.priority`: `low`, `normal`, `high`, `urgent`
- `autonomy_level`: `read`, `auto`, `confirm`, `human_only`
- `result_status`: `done`, `pending_confirmation`, `denied`, `needs_human`, `error`
- `reason_code`, `intent`: див. [06-transcript-and-analysis.md](06-transcript-and-analysis.md)

## Seed-файл: `data/seed/seed.json` (пише C, завантажує A)

Структура: об'єкт, де ключі збігаються з назвами таблиць, значення: масиви рядків таблиці
з точно такими самими іменами полів, як у `schema.sql`.

```json
{
  "users": [
    {"id": "u_demo_family", "name": "Олена Коваль", "email": "olena@example.com",
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

Правила для seed:

1. Усі дати відносно `DEMO_NOW = 2026-10-31T12:00:00Z`.
2. Обов'язково три демо-користувачі з [07-demo-scenarios.md](07-demo-scenarios.md) із зафіксованими ID.
3. Додатково 30–50 «фонових» користувачів з різними планами, станами та історією платежів.
4. `tickets`, `pending_actions`, `audit_log` у seed порожні (їх створює робота системи).
5. A пише `server/seed_loader.py`, який перевіряє seed за схемою й падає з зрозумілою помилкою.
