-- Уведомления о публикации (добавлять на действующую D1).
-- Не изменяет текущие права сотрудников и состояние публикаций.
-- События до выполнения миграции задним числом не рассылаются.

CREATE TABLE IF NOT EXISTS light_notice_config (
  id INTEGER PRIMARY KEY CHECK(id = 1),
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO light_notice_config (id) VALUES (1);

CREATE TABLE IF NOT EXISTS light_notification_receipts (
  operation_id TEXT NOT NULL REFERENCES light_operations(operation_id),
  telegram_id INTEGER NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending' CHECK (
    state IN ('pending','sending','sent','review_required')
  ),
  message_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sent_at TEXT,
  diagnostic TEXT,
  PRIMARY KEY (operation_id, telegram_id)
);

CREATE INDEX IF NOT EXISTS idx_light_notifications_state
  ON light_notification_receipts(state, created_at);
