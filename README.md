# LS VK

Приватный шлюз публикации контента во ВКонтакте для «Линии спорта».

## Что уже реализовано

- проверка подключения к VK API;
- текстовые посты на стене сообщества;
- отложенные посты через `publish_date`;
- загрузка фотографии и публикация её на стене;
- загрузка видео и публикация его на стене;
- базовая загрузка Stories;
- закрытый внутренний API с Bearer-токеном;
- секреты только через переменные окружения.

## Требования

- Node.js 20+;
- ID сообщества VK;
- токен сообщества;
- для части операций загрузки медиа может понадобиться пользовательский токен администратора сообщества.

## Настройка

1. Скопировать `.env.example` в `.env`.
2. Заполнить:

```env
PORT=3000
INTERNAL_API_KEY=<длинный случайный секрет>

VK_API_VERSION=5.199
VK_GROUP_ID=<положительный числовой ID сообщества>
VK_GROUP_TOKEN=<токен сообщества>
VK_USER_TOKEN=<опциональный пользовательский токен администратора>
```

`VK_GROUP_ID` указывается без минуса. Для публикации на стене шлюз сам использует `owner_id=-VK_GROUP_ID`.

Никогда не коммитить реальный `.env`.

## Запуск

```bash
npm install
npm start
```

## Проверка

```bash
curl http://localhost:3000/health
```

Проверить VK-подключение:

```bash
curl \
  -H "Authorization: Bearer $INTERNAL_API_KEY" \
  http://localhost:3000/api/vk/check
```

## Опубликовать текстовый пост

```bash
curl -X POST http://localhost:3000/api/vk/post \
  -H "Authorization: Bearer $INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Тестовая публикация"
  }'
```

Отложенная публикация:

```json
{
  "text": "Публикация по расписанию",
  "publishAt": "2026-10-06T18:00:00+03:00"
}
```

## Фото

Только загрузить:

```bash
curl -X POST http://localhost:3000/api/vk/photo \
  -H "Authorization: Bearer $INTERNAL_API_KEY" \
  -F "file=@photo.jpg"
```

Загрузить и сразу опубликовать:

```bash
curl -X POST http://localhost:3000/api/vk/photo \
  -H "Authorization: Bearer $INTERNAL_API_KEY" \
  -F "file=@photo.jpg" \
  -F "publish=true" \
  -F "text=Новая публикация"
```

## Видео

```bash
curl -X POST http://localhost:3000/api/vk/video \
  -H "Authorization: Bearer $INTERNAL_API_KEY" \
  -F "file=@video.mp4" \
  -F "name=Название видео" \
  -F "publish=true" \
  -F "text=Текст публикации"
```

## Story

```bash
curl -X POST http://localhost:3000/api/vk/story \
  -H "Authorization: Bearer $INTERNAL_API_KEY" \
  -F "file=@story.jpg" \
  -F "type=photo"
```

Для видео используйте `type=video`.

## Безопасность

Внешний доступ к шлюзу должен идти только по HTTPS.

Не использовать токены VK в URL, клиентском JavaScript или публичных репозиториях.

Для production желательно дополнительно ограничить доступ к API на уровне reverse proxy/firewall.

## Следующий этап

После получения VK Group ID и токенов:

1. добавить секреты на сервер;
2. выполнить `/api/vk/check`;
3. сделать закрытый тестовый пост;
4. отдельно проверить фото, видео и Story;
5. подключить этот API к рабочему процессу ChatGPT.
