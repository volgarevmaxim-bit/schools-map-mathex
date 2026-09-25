# -*- coding: utf-8 -*-
"""Валидатор канона и сгенерированных артефактов (замена build_places.py c assert 43).

Проверки:
  1. Структура data/entities.json: обязательные поля, типы, значения kind/source.
  2. Уникальность: id сущностей; каждая точка и каждая csv-строка ровно в одной сущности;
     name_normalized без дублей.
  3. Покрытие: kind/kind_source у 100% сущностей; счётчики _meta сходятся; kind точек
     соответствует kind сущности (наследование).
  4. Синхронность: places.json и schools_normalized.csv байт-равны сериализации канона
     (защита от ручных правок мимо канона).
  5. schools_content.json: place_ids покрывают все точки places.json без дублей.

Код возврата: 0 — зелёный, 1 — есть нарушения (для CI, вопрос Q6).
"""
import csv, io, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors, warnings = [], []

def err(msg): errors.append(msg)
def warn(msg): warnings.append(msg)

# --- 1/2/3: канон ---
canon = json.loads((ROOT / 'data' / 'entities.json').read_text(encoding='utf-8'))
meta = canon.get('_meta')
if not meta:
    err('entities.json: нет _meta')
entities = canon.get('entities', [])
if not entities:
    err('entities.json: пустой список entities')

seen_ent, seen_point, seen_row, seen_norm = {}, {}, {}, {}
kinds = Counter()
for e in entities:
    eid = e.get('id', '(no id)')
    if not eid or not isinstance(eid, str):
        err(f'сущность без id: {e.get("name")}')
        continue
    if eid in seen_ent:
        err(f'duplicate entity id: {eid}')
    seen_ent[eid] = True
    for field in ('name', 'name_normalized', 'address_normalized', 'kind', 'kind_source', 'source'):
        v = e.get(field)
        if not v or not str(v).strip():
            err(f'{eid}: пусто обязательное поле {field}')
    if e.get('kind') not in ('green', 'blue', 'red'):
        err(f'{eid}: kind={e.get("kind")!r} вне {{green,blue,red}}')
    else:
        kinds[e['kind']] += 1
    if e.get('source') not in ('mathex', 'forbes', 'both', 'map-only'):
        err(f'{eid}: source={e.get("source")!r} недопустим')
    for p in e.get('points', []):
        pid = p.get('id')
        if not pid:
            err(f'{eid}: точка без id')
        elif pid in seen_point:
            err(f'точка {pid} принадлежит двум сущностям: {seen_point[pid]} и {eid}')
        else:
            seen_point[pid] = eid
        for f_ in ('name', 'entity', 'kind', 'address', 'lat', 'lon'):
            if f_ not in p:
                err(f'{eid}: точка {pid} без поля {f_}')
        if p.get('kind') not in ('green', 'blue', 'red'):
            err(f'{eid}: точка {pid}: kind={p.get("kind")!r}')
        elif e.get('kind') and p['kind'] != e['kind']:
            warn(f'{eid}: точка {pid} kind={p["kind"]} != сущности {e["kind"]} (наследование)')
    for r in e.get('csv_rows', []):
        rid = r.get('id')
        if not rid:
            err(f'{eid}: csv-строка без id')
        elif rid in seen_row:
            err(f'csv-строка {rid} принадлежит двум сущностям: {seen_row[rid]} и {eid}')
        else:
            seen_row[rid] = eid
    nn = e.get('name_normalized', '')
    if nn in seen_norm:
        err(f'duplicate name_normalized: {nn!r} у {seen_norm[nn]} и {eid}')
    else:
        seen_norm[nn] = eid

if meta:
    c = meta.get('counts', {})
    if c.get('entities') != len(entities):
        err(f'_meta.counts.entities={c.get("entities")} != фактически {len(entities)}')
    if c.get('points') != len(seen_point):
        err(f'_meta.counts.points={c.get("points")} != фактически {len(seen_point)}')
    if c.get('csv_rows') != len(seen_row):
        err(f'_meta.counts.csv_rows={c.get("csv_rows")} != фактически {len(seen_row)}')

# parent_id: ссылка на существующую сущность; у green-программ должен быть родитель
for e in entities:
    par = e.get('parent_id')
    if par:
        if par not in seen_ent:
            err(f"{e['id']}: parent_id {par!r} не существует")
        if e.get('kind') != 'green':
            err(f"{e['id']}: parent_id есть, но kind={e.get('kind')} (родительская связь для green-программ)")

# --- 4: синхронность артефактов (та же сериализация, что в build_all.py) ---
point_by_id = {p['id']: p for e in entities for p in e.get('points', [])}
row_by_id = {r['id']: r for e in entities for r in e.get('csv_rows', [])}

want_places = json.dumps([point_by_id[pid] for pid in canon['place_order']],
                         ensure_ascii=False, indent=2) + '\n'
want_places_b = want_places.replace('\n', '\r\n').encode('utf-8')
got_places = (ROOT / 'places.json').read_bytes()
if got_places != want_places_b:
    err('places.json не совпадает с сериализацией канона (правка мимо канона?)')

COLS = ['id', 'name', 'address', 'lat', 'lon', 'mathex_url', 'source',
        'label', 'description', 'status', 'notes']
buf = io.StringIO()
w = csv.writer(buf, lineterminator='\r\n')
for rid in canon['csv_order']:
    r = row_by_id[rid]
    w.writerow([r[k] for k in COLS])
want_csv_b = (','.join(COLS) + '\r\n' + buf.getvalue()).encode('utf-8')
got_csv = (ROOT / 'schools_normalized.csv').read_bytes()
if got_csv != want_csv_b:
    err('schools_normalized.csv не совпадает с сериализацией канона')

# --- 5: schools_content.json покрытие точек ---
try:
    content = json.loads((ROOT / 'schools_content.json').read_text(encoding='utf-8'))
    pids = []
    for rec in content.get('records', []):
        pids.extend(rec.get('place_ids', []))
    dup = [p for p, n in Counter(pids).items() if n > 1]
    if dup:
        err(f'schools_content.json: place_ids задублированы: {sorted(dup)[:5]}')
    unknown = set(pids) - set(point_by_id)
    if unknown:
        err(f'schools_content.json: place_ids вне канона: {sorted(unknown)[:5]}')
    uncovered = set(point_by_id) - set(pids)
    if uncovered:
        err(f'точки без редакционной записи: {sorted(uncovered)[:5]}')
except FileNotFoundError:
    warn('schools_content.json не найден — проверка 5 пропущена')

# --- отчёт ---
print(f'entities: {len(entities)} | points: {len(seen_point)} | csv_rows: {len(seen_row)}')
print(f'kinds: {dict(kinds)}')
for w_ in warnings:
    print(f'WARN: {w_}')
if errors:
    print(f'\nFAIL: {len(errors)} ошибок:')
    for e in errors:
        print(f'  - {e}')
    sys.exit(1)
print('OK: валидация пройдена')
