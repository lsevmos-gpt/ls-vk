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

## Авторизация для публикации

Для обычной публикации **в сообщество** основным ключом является `VK_GROUP_TOKEN` —
ключ доступа сообщества из **Управление сообществом -> Работа с API -> Ключи доступа**.

VK ID-приложение `54806879` оставлено в проекте, но токены нового VK ID формата
`vk2.a.*` не следует использовать как основной ключ публикации в VK API:
на практике `wall.post` для них может возвращать ошибку 1051.

### Поддержка по типам контента

- текстовый пост на стену — `VK_GROUP_TOKEN`;
- отложенный текстовый пост — `VK_GROUP_TOKEN`;
- Stories — API-схема допускает group token, но публикация от сообщества дополнительно
  ограничена статусом сообщества;
- фото на стену — сначала пробуем ключ сообщества; VK может вернуть ошибку 27 для
  `photos.getWallUploadServer`, тогда требуется совместимый user API token;
- видео — `video.save` по схеме VK API требует user token; новый VK ID token
  использовать как такой токен нельзя.

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

```env
PORT=3000
INTERNAL_API_KEY=<длинный случайный секрет>

VK_API_VERSION=5.199
VK_GROUP_ID=<положительный числовой ID сообщества>
VK_GROUP_TOKEN=<ключ доступа сообщества>
VK_USER_TOKEN=<необязательно; только совместимый API user token для медиа>
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


## Публикация из ChatGPT через GitHub Actions

Репозиторий содержит workflow `.github/workflows/vk-publish.yml`.

Схема:

```text
ChatGPT -> queue/<job>.json -> GitHub Actions -> VK API -> results/<job>.json
```

Для работы workflow в **Settings -> Secrets and variables -> Actions** нужно создать:

- `VK_GROUP_ID` — числовой ID сообщества без минуса;
- `VK_GROUP_TOKEN` — ключ доступа сообщества (основной);
- `VK_USER_TOKEN` — необязательно, только если понадобится для фото/видео.

После этого для текстового поста достаточно добавить файл:

```json
{
  "id": "2026-10-06-test",
  "type": "post",
  "text": "Текст публикации"
}
```

в каталог `queue/`. Коммит автоматически запускает публикацию.

Для фото сначала файл помещается в `media/`, затем job с `type: "photo"`.
Поддерживается несколько фотографий.

Результат каждого запуска записывается в `results/<id>.json`. Это позволяет
проверить из ChatGPT, был ли пост действительно создан и какой ID вернул VK.

Готовые примеры находятся в каталоге `examples/`.
