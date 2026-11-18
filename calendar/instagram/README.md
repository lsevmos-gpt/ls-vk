# Instagram «Линия спорта»: планирование через Cloudflare

**С 19.11.2026 плановый выпуск Instagram перенесён с GitHub Actions на Cloudflare.**

- Планировщик: Cloudflare Worker `ls-instagram-publisher`, Cron `* * * * *` (UTC, каждую минуту).
- Очередь и подтверждения: D1 `ls-instagram-calendar`, таблицы `instagram_jobs`, `instagram_events` и `instagram_notifications`.
- Meta Graph API: закрытый RPC `LSInstagramGateway` на работающем Cloudflare-боте света. Meta-токены не копировались.
- Только утверждённые задания (`approved=1`) могут публиковаться. Видео готовится заранее, публикация подтверждается через Meta readback.
- Статусы `published`, `missed`, `failed`, `review_required` уведомляют владельца через Telegram; неопределённый ответ Meta **не повторяется автоматически**.
- Время `publish_at` сохраняется в UTC ISO 8601. Например, 18:30 по Симферополю/Москве = 15:30:00Z.
- Максимальное опоздание: 30 минут; дальше задача становится `missed`, а не публикуется произвольно.
- Для нового расписания создайте запись в **Cloudflare D1**, а не здесь. Новые файлы JSON в этом GitHub-каталоге **не импортируются автоматически**.

## Старый календарь GitHub

Файлы в `calendar/instagram/YYYY-MM/*.json` сохранены для истории и сверки. GitHub workflow `instagram-meta-calendar.yml` больше **не имеет Cron и не публикует**, а старый Python-обработчик `run` отключён. Команда preview и проверки пригодны только для анализа архивных JSON.

Публикация `new-fitness-20261118-1830` уже подтверждена Meta (Media ID `17946507618371509`) и помечена в Cloudflare D1 как `published`, чтобы исключить повтор.

## Формат нового задания

В `instagram_jobs` должны быть заполнены: уникальный `id`, `account='liniya__sporta'`, `post_type` (`reel`, `photo`, `story`, `carousel`), `publish_at` (UTC), `caption`, `media_json` (массив `[{"type":"video","url":"https://...mp4"}]`), необязательные `cover_url` и `collaborators_json`, `approved=1`, `status='scheduled'`. Для Reels требуется видео по общедоступному HTTPS-URL; Meta может принять не более трёх соавторов в текущей схеме.

Для отмены ещё не отправленного задания меняйте статус на `cancelled`; для изменения расписания используйте новое задание с уникальным ID. Не переводите `publishing`/`verifying` в `scheduled` без проверки публикации в Instagram.

**Это техническая инструкция, а не разрешение самостоятельно выпускать неутверждённые материалы.** Никогда не размещайте Meta-токены или иные секреты в публичном репозитории.
