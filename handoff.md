# Handoff — schools-map-mathex

Дата обновления: 2026-08-12

## Проект

- Сайт: https://volgarevmaxim-bit.github.io/schools-map-mathex/
- Репозиторий: https://github.com/volgarevmaxim-bit/schools-map-mathex
- Handoff: https://github.com/volgarevmaxim-bit/schools-map-mathex/blob/main/handoff.md
- Raw handoff: https://raw.githubusercontent.com/volgarevmaxim-bit/schools-map-mathex/main/handoff.md

## Ветки и актуальные refs

`main` — исходники, `gh-pages` — опубликованный сайт. Pages публикует `gh-pages` / `/(root)`.

```text
main:     d28d1954a2585d2b76798f804fc48fb866c62ffa
gh-pages: 71aba937f97030ea3e7a0b132b7099e6bacbb400
```

Последние коммиты:

```text
d28d195 fix: simplify tracks and remove Gazprom entries
71aba93 deploy: publish track and Gazprom updates
```

При следующем изменении: commit/push в `main`, затем отдельно обновить `gh-pages` и проверить live-файлы.

## Runtime-файлы

- `index.html` — оболочка, карта, навигация, разделы;
- `app.js` — Leaflet, popup, фильтры, dropdown траекторий, скрытие/восстановление;
- `places.json` — канонические физические точки карты;
- `schools_content.json` — редакционные записи и `place_ids`;
- `handoff.md` — этот файл.

Старые Markdown/GeoJSON/CSV/XLSX не определяют текущий runtime-состав.

## Текущий состав

- 45 точек карты;
- 38 редакционных записей;
- 29 строк сравнительной таблицы;
- связи карта ↔ описание: 45/45, без дублей.

Полностью удалены из карты, текста, таблицы и меню:

- Ломоносовский детский сад на Рублевке;
- Детский сад школы «Президент»;
- Детский сад Павловской гимназии;
- Дошкольное отделение Wunderpark;
- Газпром школа;
- Дошкольное отделение Газпром школы.

Не восстанавливать удалённые объекты из старого GeoJSON.

## Траектории

Dropdown «Обзор» показывает:

- IB и международное образование (4);
- Мультипрофиль (6);
- Физмат и естественные науки (9);
- Языки и гуманитарные науки (4);
- IT и инженерия (2);
- Проектное и гибкое образование (3);
- Мультипрофиль: физмат, естественные науки, языки и гуманитарные науки (1);
- Дошкольное образование (9).

В «Мультипрофиль» объединены прежние направления: «Языки и международное образование», «Проектное и международное образование» и «Математика, экономика и гуманитарные науки».

## Интерфейс

Между картой и обзором есть навигация: «Карта», «Обзор», «Школы и сады», «Скрытые».

«Обзор» сделан обычной JS-кнопкой с `aria-expanded` и `hidden`, а не `<details>`, чтобы работать в Edge. Список траекторий имеет ширину 360px, ограничение `max-height: 70vh` и внутреннюю прокрутку. Выбор пункта раскрывает соответствующий `<details>` и прокручивает к нему.

В popup и редакционном абзаце есть ссылка `скрыть`. Она убирает запись с карты, из текста, таблицы и dropdown. Раздел «Скрытые» внизу содержит `вернуть`. Состояние временное для текущей вкладки.

## Cache-busting

Текущий токен:

```text
tracks-gazprom-edge-20260812-1
```

Он используется для `app.js`, `places.json` и `schools_content.json`. При следующем runtime-изменении меняй этот токен и query-параметр script URL.

## Проверки

```bash
node --check app.js
python -m json.tool places.json > /dev/null
python -m json.tool schools_content.json > /dev/null
git diff --check
```

Покрытие карты:

```bash
python - <<'PY'
import json
p=json.load(open('places.json',encoding='utf-8'))
c=json.load(open('schools_content.json',encoding='utf-8'))
ids={x['id'] for x in p}; refs=[i for r in c['records'] for i in r['place_ids']]
assert len(p)==45 and len(c['records'])==38
assert ids==set(refs) and len(refs)==len(set(refs))
print('OK')
PY
```

Удалённые записи:

```bash
grep -R -E 'Газпром|газпром' places.json schools_content.json app.js index.html
```

Команда должна вернуть пустой результат.

## Публикация и проверка

```bash
git status --short --branch
git ls-remote origin refs/heads/main refs/heads/gh-pages
```

Проверять `index.html`, `app.js`, `places.json` и `schools_content.json` через GitHub Raw и Pages с уникальным query-параметром. Не доверять только timestamp в GitHub UI.

## Следующая сессия

Начать с этого файла: https://github.com/volgarevmaxim-bit/schools-map-mathex/blob/main/handoff.md
