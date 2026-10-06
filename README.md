# LS VK

Приватный шлюз публикации контента во ВКонтакте для «Линии спорта».

## Что реализовано

- проверка подключения к VK API;
- текстовые посты на стене сообщества;
- отложенные посты через `publish_date`;
- загрузка фотографий и публикация на стене;
- загрузка видео и публикация на стене;
- базовый endpoint Stories;
- закрытый внутренний API с Bearer-токеном;
- секреты только через переменные окружения.

## Важное про авторизацию VK API 5.199

Основным ключом публикации является **пользовательский access token администратора сообщества**.

В актуальной схеме VK API методы `wall.post`, `photos.getWallUploadServer` и `video.save`
работают с user token. Поэтому `VK_USER_TOKEN` обязателен для публикации.

`VK_GROUP_TOKEN` оставлен как необязательный дополнительный ключ и не используется
как замена user token для публикации на стене.

Для user token нужны как минимум права:

- `wall` — публикации;
- `photos` — изображения;
- `video` — видео;
- `groups` — работа с администрируемым сообществом;
- `stories` — если планируется API-публикация Stories.

Для долговременной серверной работы предпочтительна официальная OAuth-авторизация собственного приложения VK.

### Ограничение Stories

VK API указывает, что загрузка Stories с `group_id` предназначена для сообщества,
которое верифицировано или имеет специальный статус/значок «огонь». Поэтому Stories
нужно проверять отдельно на конкретном сообществе. Обычные посты, фото и видео от этого
ограничения не зависят.

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

```env
PORT=3000
INTERNAL_API_KEY=<длинный случайный секрет>

VK_API_VERSION=5.199
VK_GROUP_ID=<положительный числовой ID сообщества>
VK_USER_TOKEN=<user token администратора>
VK_GROUP_TOKEN=<необязательно>
```

`VK_GROUP_ID` указывается **без минуса**. Для стены шлюз сам использует
`owner_id=-VK_GROUP_ID`.

Никогда не коммитить реальные токены или `.env`.

## Запуск

```bash
npm install
npm start
```

## Проверка

Состояние сервиса:

```bash
curl http://localhost:3000/health
```

Проверка VK:

```bash
curl \
  -H "Authorization: Bearer $INTERNAL_API_KEY" \
  http://localhost:3000/api/vk/check
```

Ответ проверки показывает сообщество, пользователя токена и битовую маску разрешений
`account.getAppPermissions`.

## Текстовый пост

```bash
curl -X POST http://localhost:3000/api/vk/post \
  -H "Authorization: Bearer $INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Тестовая публикация"}'
```

Отложенная публикация:

```json
{
  "text": "Публикация по расписанию",
  "publishAt": "2026-10-06T18:00:00+03:00"
}
```

## Фото

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

- внешний доступ — только HTTPS;
- `.env` исключён из Git;
- токены не передавать в URL;
- не хранить токены в клиентском JavaScript;
- production API желательно дополнительно ограничить reverse proxy/firewall.

## Следующий этап

1. определить числовой ID сообщества;
2. создать собственное приложение VK;
3. получить официальный user token администратора с нужными scope;
4. сохранить секреты на сервере;
5. запустить `/api/vk/check`;
6. сделать тестовый пост;
7. проверить фото и видео;
8. отдельно проверить доступность Stories.
