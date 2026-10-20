# Самостоятельный календарь Instagram (Meta API)

Здесь автоматически появляются папки по месяцам, например `2026-11/`.
Каждый JSON-файл — отдельная утверждённая публикация.

**Создать запись без ChatGPT:** https://github.com/lsevmos-gpt/ls-vk/actions/workflows/instagram-calendar-add.yml

**Проверить ожидающие:** https://github.com/lsevmos-gpt/ls-vk/actions/workflows/instagram-meta-calendar.yml
Запустить `operation=preview`. Дата и время — по Симферополю/Москве, UTC+03:00.

**Важное:** этот репозиторий публичный. Не размещайте здесь приватные кампании, непубличные исходники, личные данные или секреты. Нужно отмечать `approved` и `public_content` только для публикаций, уже разрешённых к публичному размещению.

Расписание работает через GitHub Actions и Meta API независимо от ChatGPT, но время запуска по GitHub cron может сдвигаться. Примерный допустимый предел опоздания 15 минут; после него автоматической публикации не будет.

Полная инструкция: https://github.com/lsevmos-gpt/ls-vk/blob/main/INSTAGRAM_MONTHLY_CALENDAR.md
