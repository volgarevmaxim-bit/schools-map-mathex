# 🗺️ Карта школ Москвы (Mathex × Forbes)

**69 школ** Москвы и Московской области, собранные с [mathex.ru](https://mathex.ru/shkoly/) и рейтинга частных школ Forbes 2025, с координатами для импорта в Яндекс.Конструктор карт.

## Цветовая сегментация

| Цвет | Сегмент | Кол-во | Цена |
|------|---------|--------|------|
| 🔵 Синий (`#1e98ff`) | Mathex (муниципальные / бесплатные) | 18 | — |
| 🟡 Жёлтый (`#ffd21e`) | Forbes LOW | 9 | до 580 000 ₽/год |
| 🟠 Оранжевый (`#ff7800`) | Forbes MID | 23 | 580 000 – 1 300 000 ₽/год |
| 🔴 Красный (`#ef3c4a`) | Forbes HIGH | 19 | от 1 300 000 ₽/год |

## Файлы

| Файл | Назначение |
|------|-----------|
| `schools.geojson` | **Основной формат** — 69 Point-фич с цветом по сегменту, HTML-description, iconCaption ≤ 9 символов |
| `schools_normalized.csv` | Нормализованная таблица: 11 полей × 69 школ |
| `schools_import_yandex.csv` | Для ручного импорта в Яндекс.Конструктор (`lat;lon;description;label;number`) |
| `schools_raw.csv` | Сырой слой: 24 поля × 69 строк |
| `schools.xlsx` | Excel: 2 листа — `normalized`, `yandex_import` |
| `SUMMARY.md` | Полная сводка проекта |
| `processing_log.md` | Лог обработки конвейера |

## Как использовать

1. Откройте [карту](https://yandex.ru/maps/213/moscow/?ll=37.559085%2C55.693060&mode=usermaps&source=constructorLink&um=constructor%3Abad1775b5da47480bd8973fed0eb88a7f3af2e7cf7b5ea2ce870675577f95e90&z=10)

## Как изменить

1. Откройте [Яндекс.Конструктор карт](https://yandex.ru/map-constructor/)
2. Создайте новую карту → Импорт → выберите `schools.geojson` или скорректируйте вручную


## Источники

- [Mathex](https://mathex.ru/shkoly/) — список лучших школ Москвы
- [Forbes](https://www.forbes.ru/) — рейтинг частных школ 2025 (LOW / MID / HIGH сегменты)

## API

Геокодирование — Яндекс.Карты HTTP Geocoder API (`geocode-maps.yandex.ru/1.x/`).
Все 69 школ геокодированы, `precision=exact`, `kind=house`.
