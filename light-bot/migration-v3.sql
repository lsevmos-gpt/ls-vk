-- ЛИНИЯ СПОРТА · СВЕТ — миграция для Worker v3
-- Выполнить ОДИН РАЗ в Cloudflare D1 -> ls-light-db -> Console
-- Существующие clubs/admins/status_events/publications не удаляются и не меняются.

CREATE TABLE IF NOT EXISTS light_operations (
  operation_id TEXT PRIMARY KEY,
  telegram_id INTEGER NOT NULL REFERENCES admins(telegram_id),
  scope TEXT NOT NULL CHECK (scope IN ('club', 'all')),
  club_id TEXT REFERENCES clubs(id),
  new_status TEXT NOT NULL CHECK (new_status IN ('on', 'off')),
  processed INTEGER NOT NULL DEFAULT 0 CHECK (processed IN (0, 1)),
  changed_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS light_operation_changes (
  operation_id TEXT NOT NULL REFERENCES light_operations(operation_id),
  club_id TEXT NOT NULL REFERENCES clubs(id),
  old_status TEXT NOT NULL,
  new_status TEXT NOT NULL,
  PRIMARY KEY (operation_id, club_id)
);

CREATE INDEX IF NOT EXISTS idx_light_operations_time
  ON light_operations(created_at);

-- Проверка:
-- SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'light_%';
