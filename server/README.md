# server: MCP-сервер підтримки (зона A)

C# / .NET 10, офіційний MCP SDK (`ModelContextProtocol`), SQLite. Контракт: [`../contracts`](../contracts).

## Запуск

```bash
dotnet build server/SupportServer.slnx
dotnet test  server/SupportServer.slnx

# MCP-сервер (stdio): його запускає агент (B) командою зі змінної SERVER_COMMAND
dotnet run --project server/SupportServer -c Release

# чиста база (видаляє runtime/support.db і створює заново зі seed)
dotnet run --project server/SupportServer -c Release -- reset-db
```

Змінні оточення (всі необов'язкові): `SUPPORT_DB_PATH`, `SEED_PATH`, `DEMO_NOW` (ISO-дата або `real`).
Seed береться з `data/seed/seed.json` (від C); якщо його ще немає, використовується `server/dev-seed.json`.

## Архітектура

```
Tools  ->  ToolRunner  ->  Services  ->  Domain.Policies (guard)
 (MCP)     (контекст,       (сценарії)    (чисті правила)
           audit, формат)        |
                                 v
                      Ports: IBillingProvider, IAuditLog
                                 ^
                      Infrastructure: MockBillingProvider, SqliteAuditLog (SQLite)
```

| Шар | Папка | Відповідальність |
|-----|-------|------------------|
| Tools | `Tools/` | Тонкий шар MCP: опис інструмента й виклик `ToolRunner`. Логіки немає. |
| Application | `Application/` | `ToolRunner` (контекст сесії, audit, єдиний формат відповіді), сервіси сценаріїв, порти. |
| Domain | `Domain/` | Моделі та **чисті правила** (`RefundPolicy`, `DuplicateChargeDetector`): safety guard без залежностей, повністю тестований. |
| Infrastructure | `Infrastructure/` | SQLite, `MockBillingProvider`, `SqliteAuditLog`, завантаження seed. |
| Config | `Config/` | Бізнес-константи (`BusinessRules`) з `contracts/04-business-rules.md`. |

Ключові рішення:

1. **Guard поза LLM.** Правила це звичайний код; модель не може їх обійти промптом.
2. **Ізоляція користувача.** `user_id` задає лише `sys_set_context` (викликає B). Модель не передає його й не може діяти над чужим акаунтом.
3. **Аудит неможливо забути.** Кожен інструмент виконується через `ToolRunner`, який пише `audit_log` також для відмов.
4. **Заміна білінгу одним класом.** `IBillingProvider` це порт; `MockBillingProvider` одна з реалізацій.
5. **Єдина схема.** `contracts/schema.sql` вбудовується в збірку, тож БД завжди відповідає контракту.
6. **Перевірка тверджень моделі.** Причина `double_charge` у refund перевіряється за даними платежів.

## Статус інструментів

| Інструмент | Стан |
|------------|------|
| `sys_set_context`, `get_user_profile`, `get_payments`, `issue_refund` | готово + тести |
| `get_available_offers`, `apply_retention_offer`, `pause_subscription`, `change_plan` | далі |
| `cancel_subscription`, `confirm_action`, `reject_action` (двокроковий потік) | далі |
| `escalate_to_human` | далі |

## Як додати інструмент

1. Правило (якщо є) у `Domain/Policies/` + тест.
2. Метод у сервісі, що повертає `ToolOutcome` (`Done`, `Denied`, `HumanRequired`, `Fail`).
3. Тонкий метод у `Tools/` з `[McpServerTool]` і викликом `runner.Run(...)`.
4. Тест у `SupportServer.Tests/ToolFlowTests.cs`.
