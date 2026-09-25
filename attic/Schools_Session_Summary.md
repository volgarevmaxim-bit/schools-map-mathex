# Schools Session Summary

## Актуальное состояние на 2026-08-12

Сайт: https://volgarevmaxim-bit.github.io/schools-map-mathex/
Репозиторий: https://github.com/volgarevmaxim-bit/schools-map-mathex

Ветки: `main` — исходники, `gh-pages` — публикация.

```text
main:     d28d1954a2585d2b76798f804fc48fb866c62ffa
gh-pages: 71aba937f97030ea3e7a0b132b7099e6bacbb400
```

Текущий состав: 45 точек карты, 38 редакционных записей, 29 строк таблицы, связи 45/45 без дублей.

Удалены полностью из карты, текста, таблицы и меню: Газпром школа и её дошкольное отделение; Ломоносовский детский сад на Рублевке; Детский сад школы «Президент»; Детский сад Павловской гимназии; Дошкольное отделение Wunderpark.

Dropdown «Обзор» содержит 8 направлений. В «Мультипрофиль» объединены «Языки и международное образование», «Проектное и международное образование» и «Математика, экономика и гуманитарные науки».

Для Edge dropdown сделан JS-кнопкой с `aria-expanded`/`hidden`, шириной 360px, `max-height:70vh` и внутренней прокруткой. Он раскрывает нужный блок траектории.

Ссылки `скрыть` в popup и описаниях убирают запись с карты, из текста, таблицы и счётчиков. Нижний раздел `Скрытые` содержит `вернуть`; состояние временное.

Cache-busting token: `tracks-gazprom-edge-20260812-1`.

Проверять перед публикацией:

```bash
node --check app.js
python -m json.tool places.json > /dev/null
python -m json.tool schools_content.json > /dev/null
git diff --check
```

Покрытие должно быть 45 точек / 38 записей / 45 уникальных `place_ids`. После push в `main` отдельно обновить `gh-pages`, затем проверить Raw/API/Pages и rendered DOM.

Следующая сессия начинается с: https://github.com/volgarevmaxim-bit/schools-map-mathex/blob/main/handoff.md
