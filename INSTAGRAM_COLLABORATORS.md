# Instagram Reels с соавторами — «Линия спорта»

## Статус реализации

- **Новый отдельный маршрут:** GitHub Actions → официальный **Meta Graph API v26.0** → Instagram @liniya__sporta.
- Обычные публикации и Buffer остаются без изменений.
- Публичный Buffer GraphQL API **не имеет поля** для соавторов: передача параметра collaborators в Buffer не сработает. Используется отдельная авторизация Meta.
- Новый маршрут публикует **только Reels**, немедленно после ручного подтверждения. Автоматического расписания у него пока нет.
- Наличие кода **не означает**, что Meta-токен подключён или что публикация проверена на живом аккаунте.
- Ни одна публикация не производится во время проверок check, тестов или создания PR.

## 1. Один раз подключить Meta

Требования:
1. Instagram @liniya__sporta должен быть профессиональным аккаунтом Business или Creator, связанным с Facebook Page, к которой есть административный доступ.
2. Создать или настроить Meta developer app с **Instagram API with Facebook Login** и получить подходящий действующий user/page access token с разрешениями на публикацию. Для этого пути используются разрешения Instagram: instagram_basic, instagram_content_publish и разрешения Facebook Page по актуальным требованиям Meta: pages_show_list, pages_read_engagement. Для использования приложения вне собственных ролей Meta может потребоваться App Review.
3. Определить **IG professional account ID**, не путать с Facebook Page ID: в Graph API получить instagram_business_account.id у связанной Page.
4. В GitHub → репозиторий lsevmos-gpt/ls-vk → Settings → Secrets and variables → Actions создать **два Repository secrets**:
   - META_IG_ACCESS_TOKEN — Meta access token, никогда не вставлять в JSON-задания, сообщения или коммиты.
   - META_IG_USER_ID — числовой ID профессионального Instagram-аккаунта @liniya__sporta.

Действующий токен Buffer (BUFFER_API_KEY) не является токеном Meta и не заменяет его.
Токен может иметь срок действия. Если истёк, обновить META_IG_ACCESS_TOKEN безопасным способом.

После слияния доработки в main открыть GitHub → Actions → **Instagram Meta Collab (manual, approved)** → Run workflow → operation=check. job_id и confirmation оставить пустыми. Проверка делает только запрос чтения id,username, проверяет точное совпадение с @liniya__sporta и **ничего не публикует**.

## 2. Подготовить Reels с соавтором

Создать публично допустимое JSON-задание requests/instagram-meta/collab-YYYYMMDD-unique.json:

~~~json
{
  "id": "collab-20261021-example",
  "type": "instagram-reel",
  "postType": "reel",
  "handle": "liniya__sporta",
  "approved": true,
  "publicContent": true,
  "text": "Утверждённый текст публикации",
  "media": [
    {
      "type": "video",
      "url": "https://cdn.example.com/public-approved-reel.mp4"
    }
  ],
  "coverUrl": "https://cdn.example.com/public-approved-cover.jpg",
  "collaborators": [
    "account_one",
    "https://www.instagram.com/account_two/"
  ],
  "shouldShareToFeed": true
}
~~~

Это **пример с несуществующими URL**, не готовое задание.

- Поддерживается от **1 до 3** соавторов; допускаются @username, username и https://www.instagram.com/username/.
- Instagram username проверяется и нормализуется. Системе нужен точный аккаунт: существование, публичность и разрешение на сотрудничество проверяет Meta при публикации.
- Указывайте **публичные HTTPS-адреса** исходного Reels и обложки. Файлы должны быть доступны Meta **без авторизации**; не используйте ссылки Google Drive, ссылки с access tokens, приватные файлы или истекающие signed URLs.
- coverUrl необязателен; он позволяет предоставить обложку отдельным файлом через Meta API. Это отличается от возможностей публичного Buffer API.
- shouldShareToFeed управляет показом Reels в основной сетке.
- Важное предупреждение: **репозиторий сейчас публичный**. Не сохраняйте туда непубличные исходники, неопубликованные конфиденциальные ролики, персональные данные или коммерчески закрытые материалы. Если материал не должен быть публичным до релиза, сначала нужен приватный репозиторий или другой защищённый канал задания.
- approved=true и publicContent=true означают осознанное разрешение на публикацию только уже согласованного для публичного размещения материала. Не устанавливайте их автоматически для черновиков.

### Проверка без публикации

~~~bash
python -m unittest discover -s tests -v
python -m scripts.instagram_collab validate requests/instagram-meta/collab-YYYYMMDD-unique.json
~~~

## 3. Опубликовать

**Только после** того, как операция check успешно проверила Meta-доступ и материал согласован:

1. GitHub → Actions → **Instagram Meta Collab (manual, approved)** → Run workflow.
2. operation=publish.
3. job_id — ID из JSON, без расширения .json.
4. confirmation — точно PUBLISH_APPROVED_COLLAB.
5. GitHub Actions сначала прогоняет тесты, валидирует задачу и проверяет, что Meta-токен действительно принадлежит @liniya__sporta.
6. Перед первым запросом изменения к Meta **сохраняется в GitHub резервирование ID**: results/instagram-meta/<job_id>.json.
7. Media container создаётся с media_type=REELS, collaborators, опционально cover_url и share_to_feed; далее проверяется обработка видео до FINISHED и вызывается /media_publish.
8. Результат сохраняется в том же файле. published означает, что Meta вернула media ID, **не** что приглашения приняты.

При неизвестном исходе публикации выставляется manual_review_required. **Нельзя повторно запускать тот же job ID:** публикация могла фактически состояться. Сначала вручную проверить Instagram и только потом принимать отдельное решение.

## Ограничения

- **Stories не поддерживают соавторство**. Trial Reels с соавторами также несовместимы.
- Приглашённые аккаунты должны **принять** приглашение в Instagram. Запрос на публикацию не может гарантировать принятие.
- Публикация может не пройти из-за отсутствующих разрешений, неверного токена, неподдерживаемого формата видео, приватного или недоступного соавтора, неподходящего видео, недоступного media URL или ограничений аккаунта Meta.
- Для точного автоматического расписания понадобится надёжный планировщик публикаций. GitHub Actions по cron не гарантирует точную минуту, поэтому это пока **ручной защищённый маршрут**.
- При использовании Meta Graph API для публикации нужно соблюдать действующие требования Instagram к размерам, длительности, кодекам и частоте публикаций.

## Ссылки на официальные материалы

- Meta: https://developers.facebook.com/documentation/instagram-platform/content-publishing
- Meta Collaborators: https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-media/collaborators
- Meta Instagram API with Facebook Login: https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login
- Buffer API metadata: https://developers.buffer.com/types/InstagramPostMetadataInput.html
- Buffer Collabs UI: https://support.buffer.com/en-us/articles/scheduling-instagram-posts-reels-stories-and-notifications-3XA98S9Q5p
