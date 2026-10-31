-- Контракт: схема mock-бази (SQLite). Власник: A. Зміни лише за процедурою з README.
-- Усі дати: ISO 8601 UTC, текст, напр. '2026-10-31T12:00:00Z'.
-- ID: текст з префіксом (u_, sub_, pay_, tkt_, pa_, ses_).

PRAGMA foreign_keys = ON;

CREATE TABLE users (
  id            TEXT PRIMARY KEY,                -- u_...
  name          TEXT NOT NULL,
  email         TEXT NOT NULL UNIQUE,
  country       TEXT NOT NULL,                   -- ISO-3166 alpha-2, напр. 'UA'
  is_student    INTEGER NOT NULL DEFAULT 0,      -- 1 = статус студента підтверджено
  created_at    TEXT NOT NULL
);

CREATE TABLE subscriptions (
  id                 TEXT PRIMARY KEY,           -- sub_...
  user_id            TEXT NOT NULL UNIQUE REFERENCES users(id),
  plan               TEXT NOT NULL CHECK (plan IN ('individual','duo','family','student')),
  pending_plan       TEXT CHECK (pending_plan IN ('individual','duo','family','student')), -- зміна з наступного списання
  status             TEXT NOT NULL CHECK (status IN ('active','paused','canceled','past_due')),
  price_amount       REAL NOT NULL,              -- поточна ціна за період
  price_currency     TEXT NOT NULL DEFAULT 'USD',
  started_at         TEXT NOT NULL,
  next_billing_date  TEXT,                       -- NULL, якщо canceled
  paused_until       TEXT,                       -- заповнено, якщо status = 'paused'
  cancel_at          TEXT,                       -- заповнено, якщо скасування діє з кінця періоду
  discount_percent   INTEGER NOT NULL DEFAULT 0, -- активна знижка
  discount_payments_left INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE payments (
  id             TEXT PRIMARY KEY,               -- pay_...
  user_id        TEXT NOT NULL REFERENCES users(id),
  amount         REAL NOT NULL,
  currency       TEXT NOT NULL DEFAULT 'USD',
  kind           TEXT NOT NULL CHECK (kind IN ('renewal','plan_change','other')),
  status         TEXT NOT NULL CHECK (status IN ('succeeded','failed','refunded')),
  charged_at     TEXT NOT NULL,
  refunded_at    TEXT,
  refund_reason  TEXT
);
CREATE INDEX idx_payments_user ON payments(user_id, charged_at);

CREATE TABLE usage_stats (
  user_id               TEXT PRIMARY KEY REFERENCES users(id),
  listening_hours_30d   REAL NOT NULL DEFAULT 0,
  last_active_at        TEXT,
  devices_count         INTEGER NOT NULL DEFAULT 1,
  offline_downloads     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE retention_offers_used (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     TEXT NOT NULL REFERENCES users(id),
  offer_code  TEXT NOT NULL CHECK (offer_code IN ('discount_50_3m','free_month_1')),
  applied_at  TEXT NOT NULL
);

CREATE TABLE tickets (
  id            TEXT PRIMARY KEY,                -- tkt_...
  user_id       TEXT NOT NULL REFERENCES users(id),
  session_id    TEXT NOT NULL,
  priority      TEXT NOT NULL CHECK (priority IN ('low','normal','high','urgent')),
  category      TEXT NOT NULL,                   -- значення з enum intent (див. 06)
  summary       TEXT NOT NULL,                   -- зведення для агента-людини
  suggested_action_json TEXT,                    -- {"tool":..., "args":{...}, "rationale":..., "policy_ref":...}
  status        TEXT NOT NULL CHECK (status IN ('open','in_progress','closed')) DEFAULT 'open',
  created_at    TEXT NOT NULL
);

CREATE TABLE pending_actions (
  id            TEXT PRIMARY KEY,                -- pa_...
  session_id    TEXT NOT NULL,
  user_id       TEXT NOT NULL REFERENCES users(id),
  tool          TEXT NOT NULL,                   -- напр. 'cancel_subscription'
  args_json     TEXT NOT NULL,
  summary       TEXT NOT NULL,                   -- що саме буде зроблено, людською мовою
  proposed_at_turn INTEGER NOT NULL,             -- user_turn у момент пропозиції
  status        TEXT NOT NULL CHECK (status IN ('pending','confirmed','rejected','expired')) DEFAULT 'pending',
  created_at    TEXT NOT NULL,
  resolved_at   TEXT
);

CREATE TABLE audit_log (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  ts               TEXT NOT NULL,
  session_id       TEXT NOT NULL,
  user_id          TEXT,
  tool             TEXT NOT NULL,
  args_json        TEXT NOT NULL,
  result_status    TEXT NOT NULL CHECK (result_status IN ('done','pending_confirmation','denied','needs_human','error')),
  error_code       TEXT,
  autonomy_level   TEXT NOT NULL CHECK (autonomy_level IN ('read','auto','confirm','human_only')),
  reason_code      TEXT,                         -- причина, яку вказав агент (enum із 06)
  policy_ref       TEXT,                         -- напр. 'refund-policy#2.1'
  actor            TEXT NOT NULL CHECK (actor IN ('agent','human','system')) DEFAULT 'agent'
);
CREATE INDEX idx_audit_session ON audit_log(session_id, ts);
