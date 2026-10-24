# VK ID — проверка обновления токена через GitHub Actions

Статус: **подготовлено; реальная загрузка видео не включена**.

## Проверенные факты

- VK ID приложение: 54806879; сообщество «Линия спорта»: 48198173.
- На компьютере администратора работали users.get, account.getAppPermissions (video) и video.save (получен upload_url).
- На GitHub Actions прежний пользовательский токен vk2 принимался VK ID user_info, но VK API возвращал ошибку 5 / subcode 1130 (привязка к IP).
- Пока НЕ доказано, что обновление токена на GitHub runner устранит IP-ограничение.

## Что добавлено

- scripts/vk-refresh-lib.mjs — запрос OAuth refresh по официальному протоколу VK ID.
- scripts/vk-refresh-probe.mjs — офлайн-проверка, затем (по отдельной команде) ручное обновление и проверки VK API.
- .github/workflows/vk-refresh-probe.yml — manual-only, два режима.
- tests/vk-refresh.test.mjs — автономные тесты без VK и без секретов.

Публикация и видеозагрузка этой проверкой не выполняются. Существующие
workflow, расписания и ключ сообщества не меняются.

## Секреты, необходимые только для реальной проверки

Настройки репозитория: https://github.com/lsevmos-gpt/ls-vk/settings/secrets/actions

1. VK_REFRESH_TOKEN — refresh_token из приватного комплекта авторизации
   vk.liniyasporta.ru (не старый access_token).
2. VK_DEVICE_ID — device_id из ТОЙ ЖЕ выдачи токена.
3. VK_SECRETS_WRITE_PAT — отдельный fine-grained GitHub PAT пользователя
   lsevmos-gpt, только репозиторий ls-vk, разрешения Secrets: Read and write
   (Metadata: Read). Этот токен нужен для обновления GitHub repository secret
   после возможной ротации refresh_token. Обычного GITHUB_TOKEN недостаточно.

Никогда не коммитить приватный комплект, код авторизации, device_id, PAT
или токены в публичный репозиторий и не публиковать их в чате.

## Запуск

Ссылка: https://github.com/lsevmos-gpt/ls-vk/actions/workflows/vk-refresh-probe.yml

1. Офлайн: Run workflow -> main -> mode = offline -> confirm = пусто.
   Код проверяется без VK и секретов. Признак: VK_REFRESH_OFFLINE=PASS.
2. После добавления трёх секретов — тот же workflow:
   mode = refresh_and_check; confirm = ROTATE_REFRESH_TOKEN.
   Запуск разрешён только владельцу lsevmos-gpt на ветке main.

## Безопасная последовательность live

1. Проверить контекст GitHub и наличие трёх секретов.
2. ДО обращения к VK проверить возможность изменения секретов GitHub
   созданием и удалением временного VK_REFRESH_WRITE_PROBE.
3. Вызвать POST https://id.vk.ru/oauth2/auth с grant_type=refresh_token,
   client_id, redirect_uri, device_id, state в query и refresh_token в body.
4. Проверить возвращённые access_token, refresh_token и state, без логирования.
5. Немедленно сохранить новый VK_REFRESH_TOKEN как GitHub Secret.
6. Только потом выполнить read-only методы VK ID user_info, VK API users.get
   и account.getAppPermissions. Метод video.save не вызывается.

Успех: VK_REFRESH_TOKEN_PERSIST=OK, VK_ID_USER_INFO=OK,
VK_API_USERS_GET=OK, VK_API_VIDEO_PERMISSION=YES,
VK_GITHUB_SAME_RUNNER_ACCESS=PASS.

Если опять ошибка 5 / subcode 1130 — гипотеза обновления токена на
динамическом runner не подтвердилась. Повторять refresh без причины не нужно.

## Ограничения

VK может ротировать refresh_token. Если runner сломается между ответом VK
и записью нового секрета GitHub, автоматическое восстановление невозможно
без дополнительной схемы резервирования. Тест включает предварительную
проверку прав на запись, но не устраняет полностью этот аварийный промежуток.

GitHub-hosted runners имеют меняющиеся исходящие IP. Успех одного запуска
доказывает доступ с того runner'а, но НЕ подтверждает работу будущих запусков
после смены IP. Не включать автоматическую публикацию до проверки.

Примечание: redirect_uri в workflow сейчас:
https://vk.liniyasporta.ru/oauth/callback
Он должен совпадать с тем, который использовался при исходной авторизации.
При несовпадении исправить в workflow ДО live-теста.

Официальный исходный код VK ID SDK:
https://github.com/VKCOM/vkid-web-sdk/blob/master/src/auth/auth.ts
GitHub Secrets API:
https://docs.github.com/en/rest/actions/secrets
