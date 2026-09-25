# AUDIT HANDOFF — schools-map-mathex: аудит (Фаза А)

**Дата:** 2026-09-25. **Статус: ЗАВЕРШЕНО. Фаза А (Gate 1 ✓) + Фаза Б (REVIEW_KIND закрыт 2026-09-25 ✓) влиты в main: merge `bacc480`, gh-pages синхронна `4910b87` (runtime байт-идентичен, live проверен). Снапшот openhouse-radar обновлён (@4196161): entities.json + CSV + places.json, SHA в data/raw/UPSTREAM.md.**
**Ветка:** `audit/phase-a` (read-only аудит; main не тронут). Снапшот: `main @830f792` = актуальный origin/main.
**Имя файла:** сознательно `AUDIT_HANDOFF.md` (не `HANDOFF.md`) — в репо уже живёт runtime-файл `handoff.md`, и на case-insensitive Windows FS имена конфликтуют.

## Что сделано

- `AUDIT.md` — полный отчёт Фазы А: lineage-карта (20 файлов), match-отчёт CSV↔places (A2), модель сущностей и дубли (A3), ревизия 45 меток kind vs хардкоды (A4), реестр дефектов D1–D12 с severity (A5).
- `audit/match_audit.py` — воспроизводимый матчинг: нормализация + fuzzy + containment/номера + haversine, 1:1 жадный, два прохода (match → unsure).
- `audit/kind_audit.py` — сверка kind с GREEN/BLUE-хардкодами build_data.py.
- `audit/match_report.csv` — машиночитаемый, 69 строк, колонки по ТЗ §4 А2 (вход Этапа 1 радара).

## Ключевые цифры

- Матчинг: **23 match / 2 unsure / 44 no_match**; покрытие точек 24/45.
- Blue: 3 точки карты, сматчена **1** («Интеграция XXI век»); 548 Царицыно и ТОР IT SCHOOL в CSV отсутствуют. Метрика радара §6.2 = 33% (норма ≥90%) — без Фазы Б недостижима.
- CSV-дубль: ЦПМ ×2 (mathex-skola-cpm = forbes-mid-23) → в каноне 68 сущностей из 69 строк.
- kind: 26 green / 16 red / 3 blue; 11 групп из 2–3 точек; кейс Летово: метки расходятся внутри школы (green,green,red).
- BLUE-хардкод = 15 имён ⊃ GREEN (11); ни одна из 3 текущих blue в него не входит.
- Гипотеза S1 подтверждена; S6 частично опровергнута (handoff'ы описывают одинаковый состав 45/38/29).

## Опасное (не запускать)

- `python build_data.py` — **перезапишет app.js** в старый формат (const PLACES) и сломает сайт. Скрипт несовместим с текущим runtime.
- `python build_places.py` — упадёт на `assert len(data)==43` (фактически 45).

## Следующий шаг

1. Владелец читает AUDIT.md → Gate 1.
2. После «ок» — Фаза Б по ТЗ §5 (entities.json, backfill kind, build_all.py, validate.py, чистка) в feature-ветке; решения по Q1–Q7 (сводка: AUDIT.md, раздел «Входы для Фазы Б»).
3. Радар остаётся в паркинге до завершения Фазы Б.

---

## Фаза Б (2026-09-25, ветка refactor/canon, pushed)

- `data/entities.json` — канон: **73 сущности** (68 из CSV с дедупом ЦПМ×2 и кластеризацией Ломоносовской×3 + 8 map-only групп, MCS Polyanka слита по associated_school), 69/69 csv-строк, 45/45 точек.
- `scripts/build_all.py` — places.json + schools_normalized.csv из канона, байт-идентично (md5 verified), идемпотентно (0 diff).
- `scripts/validate.py` — зелёный: схема, уникальность, покрытие, синхронность канон↔артефакты, place_ids контента.
- Backfill kind: blue=19 / red=54 по правилам (текст приёма с 1 класса из schools_content.table, NEG-aware; legacy BLUE-хардкод; kindergarten→green). У каждой сущности kind_source.
- `REVIEW_KIND.md` — пачка из 20 позиций на ревью владельца (Gate 2).
- Зомби-артефакты → `attic/` (реверсибельно), README/handoff актуализированы.
- runtime-файлы (index.html, app.js, places.json, schools_content.json) байт-идентичны main.

**Ревью владельца 2026-09-25 (закрыто):** Q2 = «blue в принципе»; web-вердикты: Еврогимназия/Wunderpark/CIS → blue, ЦПМ → red (с 5 класса), Летово → blue (Джуниор набирает 1 класс), 1543 → blue (mos.ru), Золотое сечение → blue, Хорошкола → blue (подтв.), Дюма → blue. Структурно: «Интек» и «Зеленый мыс» — отдельные сущности (red, флаг «проверить при развитии»); все 9 детсад-программ — отдельные green-сущности с parent_id (требование владельца: «всё интересное родителям первоклассника должно отражаться» — радар больше не теряет сады).

**Итог канона:** 84 сущности — blue=22, red=53, green=9; 69/69 csv-строк; 45/45 точек; validate.py зелёный (включая parent_id); build_all идемпотентен (0 diff); runtime-файлы байт-идентичны main.

**Дальше:** merge `refactor/canon` → main по команде владельца; обновление gh-pages; радар обновляет снапшот (§6.4).
