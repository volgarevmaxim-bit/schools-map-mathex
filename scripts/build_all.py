# -*- coding: utf-8 -*-
"""Генерация живых артефактов из канона data/entities.json.

Выход: places.json, schools_normalized.csv — байт-идентичны текущим (снапшот @830f792):
  places.json = json.dumps(ensure_ascii=False, indent=2) + '\\n', переведённое в CRLF;
  schools_normalized.csv = header + csv.writer(lineterminator='\\r\\n') (описания содержат \\n в кавычках).
Идемпотентность: повторный запуск = 0 diff (проверка: git status после двойного запуска).

Не генерируется (ручной редакторский контент): schools_content.json, app.js, index.html.
"""
import csv, io, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON = ROOT / 'data' / 'entities.json'

canon = json.loads(CANON.read_text(encoding='utf-8'))
order_p = canon['place_order']
order_c = canon['csv_order']

# --- places.json ---
point_by_id = {}
for e in canon['entities']:
    for p in e['points']:
        if p['id'] in point_by_id:
            raise SystemExit(f'duplicate point id in canon: {p["id"]}')
        point_by_id[p['id']] = p
missing_p = [pid for pid in order_p if pid not in point_by_id]
extra_p = set(point_by_id) - set(order_p)
if missing_p or extra_p:
    raise SystemExit(f'place_order mismatch: missing={missing_p} extra={sorted(extra_p)}')
places = [point_by_id[pid] for pid in order_p]

text = json.dumps(places, ensure_ascii=False, indent=2) + '\n'
(ROOT / 'places.json').write_bytes(text.replace('\n', '\r\n').encode('utf-8'))

# --- schools_normalized.csv ---
row_by_id = {}
for e in canon['entities']:
    for r in e['csv_rows']:
        if r['id'] in row_by_id:
            raise SystemExit(f'duplicate csv row id in canon: {r["id"]}')
        row_by_id[r['id']] = r
missing_c = [rid for rid in order_c if rid not in row_by_id]
extra_c = set(row_by_id) - set(order_c)
if missing_c or extra_c:
    raise SystemExit(f'csv_order mismatch: missing={missing_c} extra={sorted(extra_c)}')

COLS = ['id', 'name', 'address', 'lat', 'lon', 'mathex_url', 'source',
        'label', 'description', 'status', 'notes']
buf = io.StringIO()
w = csv.writer(buf, lineterminator='\r\n')
for rid in order_c:
    r = row_by_id[rid]
    w.writerow([r[k] for k in COLS])
csv_text = ','.join(COLS) + '\r\n' + buf.getvalue()
(ROOT / 'schools_normalized.csv').write_bytes(csv_text.encode('utf-8'))

n_points = len(places)
n_rows = len(order_c)
n_ent = len(canon['entities'])
print(f'entities: {n_ent} | places.json: {n_points} objects | schools_normalized.csv: {n_rows} rows')
