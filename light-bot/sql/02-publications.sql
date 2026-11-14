-- ЛИНИЯ СПОРТА / Свет — таблица заданий на сторис.
-- Не изменяет существующие таблицы/роли/статусы.
-- ВАЖНО: enabled=0 -> никаких публикаций до отдельного разрешения.
CREATE TABLE IF NOT EXISTS light_publish_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1))
);
INSERT OR IGNORE INTO light_publish_settings (id, enabled) VALUES (1, 0);

CREATE TABLE IF NOT EXISTS light_publication_jobs (
  job_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL REFERENCES light_operations(operation_id),
  scope TEXT NOT NULL CHECK(scope IN ('club','all')),
  club_id TEXT,
  new_status TEXT NOT NULL CHECK(new_status IN ('on','off')),
  platform TEXT NOT NULL CHECK(platform IN ('instagram','vk')),
  asset_key TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN
   ('queued','preparing','processing','ready','publishing','submitted',
    'published','review_required','failed','superseded')),
  container_id TEXT,
  upload_result TEXT,
  external_id TEXT,
  verification_attempts INTEGER NOT NULL DEFAULT 0,
  diagnostic TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(operation_id, platform)
);
CREATE INDEX IF NOT EXISTS idx_light_publication_jobs_queue
  ON light_publication_jobs (state, created_at);

-- Триггер добавляет 2 задания атомарно с изменением статусов.
-- При «Все клубы» создаёт одну общую сторис для каждой соцсети.
-- Исторические операции не затрагиваются.
CREATE TRIGGER IF NOT EXISTS light_enqueue_after_operation
AFTER UPDATE OF processed ON light_operations
WHEN OLD.processed = 0 AND NEW.processed = 1 AND NEW.changed_count > 0
 AND (SELECT enabled FROM light_publish_settings WHERE id = 1) = 1
BEGIN
  INSERT OR IGNORE INTO light_publication_jobs
    (job_id, operation_id, scope, club_id, new_status, platform, asset_key)
  SELECT NEW.operation_id || ':instagram', NEW.operation_id,
    NEW.scope, NEW.club_id, NEW.new_status, 'instagram',
    CASE WHEN NEW.scope = 'all'
      THEN 'all-' || NEW.new_status
      ELSE NEW.club_id || '-' || NEW.new_status END;
  INSERT OR IGNORE INTO light_publication_jobs
    (job_id, operation_id, scope, club_id, new_status, platform, asset_key)
  SELECT NEW.operation_id || ':vk', NEW.operation_id,
    NEW.scope, NEW.club_id, NEW.new_status, 'vk',
    CASE WHEN NEW.scope = 'all'
      THEN 'all-' || NEW.new_status
      ELSE NEW.club_id || '-' || NEW.new_status END;
END;