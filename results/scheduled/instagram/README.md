# Журнал автоматических публикаций Instagram

Здесь GitHub Actions сохраняет результаты публикаций из самостоятельного календаря
[calendar/instagram](https://github.com/lsevmos-gpt/ls-vk/tree/main/calendar/instagram).

Возможные статусы:

- `submission_started` — зарезервировано до отправки в Meta, повторять нельзя;
- `published` — Meta вернула Instagram media ID;
- `manual_review_required` — результат неизвестен, нужна проверка Instagram;
- `missed_window` — планировщик опоздал более чем на 15 минут, ничего не отправлял.

Отсутствие записи означает, что публикация ещё не обработана. В случае
`manual_review_required` сначала проверить Instagram; не удалять журнал и
не повторять задание автоматически.

Планы: https://github.com/lsevmos-gpt/ls-vk/tree/main/calendar/instagram
