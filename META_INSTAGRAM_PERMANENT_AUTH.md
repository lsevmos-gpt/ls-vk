# Meta Instagram: долговременная авторизация «Линия спорта»

**Цель:** прямая публикация через официальный Meta Graph API, без зависимости от Buffer/Metricool.

**Объекты и путь интеграции:**
- Приложение Meta: `Liniya Sporta Social API`
- Facebook Page `Liniya sporta` — `1309947522200598`
- Instagram Business `@liniya__sporta` — `17841458490047255`
- GitHub: `lsevmos-gpt/ls-vk`; секреты `META_IG_ACCESS_TOKEN`, `META_IG_USER_ID`.
- Используем **Instagram API with Facebook Login** и `graph.facebook.com`; нельзя без переписывания кода подставлять сюда токен из нового Instagram Login (`graph.instagram.com`).

## Инцидент 20.10.2026

В 11:19 МСК прямое Meta API успешно опубликовало LADY DANCE.
В 12:00 МСК прежний токен перестал действовать; API вернул HTTP 401 / code 190:
`Session has expired on Tuesday, 20-Oct-26 02:00:00 PDT`.

Изначально был создан **Page Access Token на базе короткоживущего User Access Token, полученного в Graph API Explorer**. Стандартные Page токены тоже бывают короткоживущими, если базовый User токен не продлевали заранее.

Источник Meta: https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived

## Вариант A — исправить существующий маршрут без изменения кода (основной)

1. Администратор открывает https://developers.facebook.com/apps и приложение `Liniya Sporta Social API`. На странице **App Settings → Basic** доступен App ID и, после повторной проверки владельца, App Secret. **App Secret не отправлять в чат, публичные URL, JSON или GitHub файлы.**
2. В https://developers.facebook.com/tools/explorer заново получить *User Access Token* для **этого же приложения** под пользователем, управляющим Facebook Page. Разрешения для действующего маршрута: `pages_show_list`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`.
3. **Перед запросом Page token** преобразовать User token в long-lived (~60 дней) на сервере:
   `GET https://graph.facebook.com/v26.0/oauth/access_token` с параметрами `grant_type=fb_exchange_token`, `client_id`, `client_secret`, `fb_exchange_token`. Ключи передаются только через безопасную серверную сессию, а не добавляются в публичную ссылку или GitHub. Если Meta Access Token Debugger предлагает официальную функцию Extend Access Token, можно использовать её, затем перепроверить срок.
4. С новым **long-lived User Access Token** сделать `GET /me/accounts?fields=id,name,access_token,instagram_business_account`; выбрать только Page ID `1309947522200598` и убедиться в соответствии IG `17841458490047255`.
5. Взять из этой записи **новый Page Access Token**, НЕ долгосрочный User токен. Проверить в https://developers.facebook.com/tools/debug/accesstoken:
   - `Is Valid: True`
   - `Expires: Never` / нет установленной даты окончания
   - требуемые разрешения и нужное приложение;
   - доступ к правильной странице и Instagram Business.
   Если дата окончания есть, **не** считать токен постоянным — вернуться к пунктам 3–4.
6. В GitHub → https://github.com/lsevmos-gpt/ls-vk/settings/secrets/actions → **Repository secrets** заменить `META_IG_ACCESS_TOKEN` на итоговый Page token; `META_IG_USER_ID` оставить `17841458490047255`.
7. Рекомендуется также добавить `META_APP_ID` и `META_APP_SECRET` как **GitHub Secrets**, чтобы монитор мог **только читать** `/debug_token` и заранее предупреждать о дате истечения или data-access expiration. Не публиковать App Secret нигде.
8. Запустить **Instagram Meta credential check (read only)** → **Run workflow**: https://github.com/lsevmos-gpt/ls-vk/actions/workflows/meta-ig-readiness.yml. Ожидаемый результат: `META_ACCOUNT_OK @liniya__sporta`, валидный токен и отсутствие скорого истечения. Контроль не публикует контент.

Meta подтверждает: Page token, созданный на основе **long-lived User token**, не имеет заданной даты истечения, но может потерять действительность при отзыве доступа, смене прав/связки бизнес-активов или изменениях безопасности.

Просроченный токен от 20 октября повторно продлить нельзя; нужен новый User token.

## Вариант B — корпоративный System User

Если приложение и Page принадлежат бизнес-портфелю компании, можно вместо привязки к личному пользователю использовать техническую учётную запись **System User**:

- https://business.facebook.com/settings/ → Users → System Users → создать сотрудника-робота для публикаций.
- Назначить ему приложение и связанные бизнес-активы (страницу `Liniya sporta` и Instagram `@liniya__sporta`) с достаточными задачами на создание контента.
- Создать системный токен для приложения с разрешениями, требуемыми Instagram API with Facebook Login, и проверить, что именно он работает с `GET /{ig-user-id}?fields=id,username`.
- Если Meta предлагает **Never** для этого вида токена — можно его использовать; некоторые Business-аккаунты могут требовать токен с ограничением в 60 дней.
- Если срок 60 дней, необходимо настроить безопасную **ротацию ДО истечения** (Meta `fb_exchange_token` для expiring system user) и защищённое обновление secret. Обязательно предусмотреть аварийную перепривязку и уведомления.

**Не подменять токен Instagram Login (`graph.instagram.com`) в существующем Facebook-Login коде**: это разные схемы авторизации, разрешения и точки API.

## Уже сделанная профилактика

- В `.github/workflows/meta-ig-readiness.yml` проверка прямого API теперь каждый час (best-effort GitHub cron), только GET.
- `scripts/meta_ig_token_health.py`: сверка `id,username` с целевым Instagram и, если добавлены App ID/Secret, проверка `debug_token` и предупреждение за 14 дней до даты истечения токена или срока доступа к данным.
- При ошибке job помечается Failed; GitHub Actions Alerts/Notifications зависят от настроек учётной записи. Даже токен без даты истечения периодически проверяется, поскольку его могут отозвать.
- Монитор никогда не публикует, не удаляет, не повторяет посты и не печатает секреты.
- GitHub Actions cron не даёт гарантии запуска с точностью до минуты; его нельзя приравнивать к серверу с SLA.

## Дополнительная безопасность

- Весь `ls-vk` — публичный репозиторий: ни токены, ни App Secret, ни приватные исходники не должны попадать в commit, issue, PR или комментарий.
- Проверять доступ и тип токена **перед** любым согласованным заданием на публикацию.
- При `190`, недостающем scope, отмене доступа или неверном IG ID **блокировать публикацию**, исправлять авторизацию и не повторять неоднозначную отправку.
- Токен со статусом `Expires: Never` не означает абсолютную гарантию вечной работоспособности API: Meta может отозвать токен или изменить свои правила.

Официальное руководство Meta: https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived

Официальная коллекция API от Meta: https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api
