# README — schools-map-mathex

Статический сайт-карта школ и детских садов Москвы (Leaflet, GitHub Pages):
https://volgarevmaxim-bit.github.io/schools-map-mathex/

## Дата-флоу (после рефакторинга Фазы Б)

```
data/entities.json          ← канон: 73 сущности (школы/сады), точки, csv-строки, kind + kind_source
      │
      ├── scripts/build_all.py ──► places.json            (45 точек, runtime карты)
      │                         └─► schools_normalized.csv (69 строк, upstream-реестр)
      ├── scripts/validate.py    проверка канона + байт-синхронности артефактов (exit 1 для CI)
      └── schools_content.json   редакторский контент (ручной, не генерируется)
```

- **Канон — `data/entities.json`**: единственный ручной источник данных. `kind` живёт на
  сущности, точки наследуют. Поля сущности: `id, name, name_normalized, address_normalized,
  kind, kind_source, points[], csv_rows[], source` (+ опц. `kind_review`, `mathex_url`).
- **Генерация**: `python scripts/build_all.py` — пишет `places.json` и
  `schools_normalized.csv` байт-идентично (идемпотентно: повторный запуск = 0 diff).
- **Валидация**: `python scripts/validate.py` — схема/уникальность/покрытие, байт-сверка
  артефактов с каноном (ручные правки places.json/csv мимо канона ломают валидацию).
- **Runtime сайта**: `index.html` + `app.js` (fetch `places.json` и `schools_content.json`,
  cache-busting через `ASSET_VERSION`). **Не редактируйте places.json руками** — правьте
  канон и перегенерируйте.
- **Миграция** в канон (историческая, однократная): `scripts/migrate_to_entities.py`.

## Метки kind

- `blue` — школа ведёт documented приём в 1 класс (текст приёма в `schools_content.json.table`
  либо legacy-хардкод `build_data.py`; итог — в `kind_source` каждой сущности);
- `green` — сущность-детский сад (программа);
- `red` — школа из списка без сигнала приёма с 1 класса.

Сомнительные метки — в `REVIEW_KIND.md` (пачка ревью владельца). Точки хранят legacy
`kind` для цветов живой карты; метка сущности — для downstream (openhouse-radar берёт
`id, name, address, kind, kind_source`).

## Публикация

GitHub Pages публикует ветку `gh-pages` (`/(root)`). После коммита в `main` обновить
`gh-pages` и проверить live-версии `index.html`, `app.js`, `places.json`,
`schools_content.json` (md5). Автоматизация публикации — в backlog.

## Архив

`attic/legacy-2026-06/` — артефакты пайплайна 17.06 (geojson/xlsx/yandex-import/SUMMARY/
processing_log/build_data/build_places): историческая ценность, в runtime не участвуют.
`attic/Schools_Session_Summary.md` — дублирующий handoff 12.08 (канонический — `handoff.md`).
`attic/` можно удалить без последствий для сайта и дата-флоу.
