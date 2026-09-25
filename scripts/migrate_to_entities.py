# -*- coding: utf-8 -*-
"""Миграция (однократная): CSV 69 + places.json 45 + match_report + schools_content
→ канонический реестр data/entities.json.

Правила (детерминированные, решение владельца поверх — через ревью REVIEW_KIND.md):
- CSV-сущности: дедуп по нормализованному имени (ЦПМ x2 -> 1).
- Точки: place из match/unsure -> точка своей сущности; места той же `group`
  присоединяются, если у группы одна CSV-сущность; оставшиеся места -> сущности по group.
- kind: 1) единодушие точек -> наследуется; 2) текст приёма с 1 класса (content.table);
  3) legacy BLUE\\GREEN-хардкод; иначе red (легенда сайта: 'Школа из списка').
- Конфликты -> kind_review=true + запись в REVIEW_KIND.md.
"""
import csv, json, re, io
from pathlib import Path
from collections import OrderedDict

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data'
OUT.mkdir(exist_ok=True)
SNAP = '@830f792'

# ---------- нормализация (из аудита) ----------
STOP = {'гбоу', 'ано', 'по', 'чоу', 'им', 'имени', 'г.', 'гор.'}
def norm_name(s):
    s = (s or '').lower().replace('ё', 'е')
    s = re.sub(r'[«»"\'\(\)\[\].,!?—–/-]', ' ', s)
    s = s.replace('№', ' no ')
    s = re.sub(r'\bшкола[\s-]+пансион\b', ' ', s)
    return ' '.join(t for t in s.split() if t and t not in STOP)

def norm_addr(s):
    s = (s or '').lower().replace('ё', 'е')
    s = re.sub(r'[«»"\'\[\]]', ' ', s)
    for a, b in [('улица','ул'),('проспект','пр'),('переулок','пер'),('шоссе','ш'),
                 ('бульвар','бул'),('набережная','наб'),('корпус','к'),('корп.','к'),
                 ('строение','с'),('деревня','д'),('город','')]:
        s = s.replace(a, b)
    s = re.sub(r'[.,]', ' ', s)
    s = re.sub(r'\bмосква\b|\bмосковская область\b', ' ', s)
    s = re.sub(r'(\d)\s*([а-я])\b', r'\1\2', s)
    return ' '.join(t for t in s.split() if t)

def slugify(name):
    s = norm_name(name)
    s = re.sub(r'\bno\b', '', s)
    s = re.sub(r'[^а-яa-z0-9]+', '-', s).strip('-')
    return s or 'entity'

GENERIC_TOKENS = {'школа', 'no', 'им', 'имени', 'пансион', 'мбоу', 'часть'}
BLUE_LEGACY = {'Школа 57', 'Президент', 'Brookes Moscow', 'Cambridge International School',
               'Английская школа MCS', 'Европейская гимназия', 'Интеграция XXI век',
               'Школа 1514', 'Курчатовская школа', 'Павловская гимназия',
               'Ломоносовская школа', 'Хорошкола', 'Новая школа', 'Золотое сечение',
               'Wunderpark International School'}

POS = re.compile(r'(?:с|со|в)\s+1\s*(?:го)?\s*класса?\b|с первого класса|перв(?:ый|ого)\s+класс\b|(?:^|[.;])\s*1\s*класса?\b', re.I)
NEG = re.compile(r'не подтвержд|не является|не предусмотрен|не относится|не заявлен|не найден', re.I)

def admission_positive(text):
    if not text:
        return None
    m = POS.search(text)
    if not m:
        return None
    ctx = text[max(0, m.start()-60):m.start()] + ' ' + text[m.end():m.end()+60]
    if NEG.search(ctx):
        return None
    return text.strip()

def hardcode_hits(entity_name, hardset):
    et = set(norm_name(entity_name).split())
    hits = []
    for h in sorted(hardset):
        ht = [t for t in norm_name(h).split() if t not in GENERIC_TOKENS]
        if ht and all(t in et for t in ht):
            hits.append(h)
    return hits

# ---------- входы ----------
rows = list(csv.DictReader(open(ROOT/'schools_normalized.csv', encoding='utf-8')))
places = json.load(open(ROOT/'places.json', encoding='utf-8'))
place_by_id = {p['id']: p for p in places}
report = list(csv.DictReader(open(ROOT/'audit'/'match_report.csv', encoding='utf-8-sig')))
content = json.load(open(ROOT/'schools_content.json', encoding='utf-8'))
table = {t['school']: t for t in content.get('table', [])}
place_group = {p['id']: p.get('group', p['name']) for p in places}
place_ids_by_group = {}
for p in places:
    place_ids_by_group.setdefault(p.get('group', p['name']), []).append(p['id'])

# ---------- 1. CSV-сущности по нормализованному имени ----------
csv_entities = OrderedDict()   # key -> {'rows': [...], 'name': ...}
for r in rows:
    k = norm_name(r['name'])
    csv_entities.setdefault(k, {'rows': [], 'name': r['name']})['rows'].append(r)

# матч-отчёт: csv_id -> (place_id, verdict)
match_of_row = {r['csv_id']: (r['place_id'], r['verdict']) for r in report if r['place_id']}
row_id_of_key = {}
for k, v in csv_entities.items():
    for r in v['rows']:
        row_id_of_key[r['id']] = k

key_group = {}   # key -> группа сматченных точек (только если все они в одной группе)
for k, v in csv_entities.items():
    gs = {place_group[match_of_row[r['id']][0]] for r in v['rows'] if r['id'] in match_of_row}
    if len(gs) == 1:
        key_group[k] = gs.pop()

# кластеризация: ключи, сматченные в одну и ту же группу, сливаются в одну csv-сущность
# (Ломоносовская школа x3 строки -> 1 сущность; ЦПМ mathex+forbes -> 1 сущность)
group_keys = {}
for k, g in key_group.items():
    group_keys.setdefault(g, []).append(k)
cluster_of = {}   # key -> cluster id (кортеж ключей, отсортированный)
seen_clusters = []
for k in csv_entities:
    if k in cluster_of:
        continue
    g = key_group.get(k)
    if g is not None:
        members = tuple(sorted(group_keys[g]))
    else:
        members = (k,)
    for m in members:
        cluster_of[m] = members
    if members not in seen_clusters:
        seen_clusters.append(members)

def unsure_links(members):
    out = []
    for k in members:
        for r in csv_entities[k]['rows']:
            m = match_of_row.get(r['id'])
            if m and m[1] == 'unsure':
                p = place_by_id[m[0]]
                out.append(f"unsure link: {r['id']} «{r['name']}» → {m[0]} ({p['address']})")
    return out

# ---------- 2. распределение точек ----------
taken_place, cluster_points = set(), {}   # cluster -> [place dicts]
for members in seen_clusters:
    pids = []
    for k in members:
        for r in csv_entities[k]['rows']:
            if r['id'] in match_of_row:
                pid = match_of_row[r['id']][0]
                if pid not in taken_place:
                    pids.append(pid); taken_place.add(pid)
    g = key_group.get(members[0])
    if g is not None:
        for pid in place_ids_by_group.get(g, []):
            if pid not in taken_place:
                pids.append(pid); taken_place.add(pid)
    cluster_points[members] = [p for p in places if p['id'] in pids]

place_only_groups = [g for g, ids in place_ids_by_group.items()
                     if all(pid not in taken_place for pid in ids)]
mixed_groups = [g for g, ids in place_ids_by_group.items()
                if any(pid in taken_place for pid in ids) and any(pid not in taken_place for pid in ids)]

# ---------- 3. сборка канона ----------
entities = []
used_ids = set()

def unique_id(base):
    i, cid = 2, base
    while cid in used_ids:
        cid = f'{base}-{i}'; i += 1
    used_ids.add(cid)
    return cid

for members in seen_clusters:
    pts = cluster_points[members]
    src_rows = [r for k in members for r in csv_entities[k]['rows']]
    srcs = {r['source'] for r in src_rows}
    source = 'both' if len(srcs) > 1 else srcs.pop()
    g = key_group.get(members[0])
    groups = sorted({place_group[p['id']] for p in pts})
    name = g if (g and pts) else src_rows[0]['name']
    if not g and len(members) > 1:
        name = max((r['name'] for r in src_rows), key=len)
    trow = table.get(name) or next((table[gr] for gr in groups if gr in table), None)
    a1 = admission_positive(trow.get('admission')) if trow else None
    r2 = hardcode_hits(name, BLUE_LEGACY)
    pk = {p['kind'] for p in pts}
    flags = []
    for link in unsure_links(members):
        flags.append(link)
    allkg = bool(pts) and all(p['entity'] == 'kindergarten' for p in pts)
    if allkg:
        kind = 'green'
        ksrc = f'kindergarten program (places.json {SNAP})'
    elif a1:
        kind = 'blue'
        ksrc = f'rule:content-admission ({name} in schools_content.table {SNAP})'
    elif r2:
        kind = 'blue'
        ksrc = f'rule:legacy-build_data.py BLUE\\GREEN ({", ".join(r2)})'
    else:
        kind = 'red'
        ksrc = 'default: школа из списка (легенда red); сигналов blue нет'
    if pts and not allkg:
        disagree = sorted({f"{p['id']}={p['kind']}" for p in pts if p['kind'] != kind})
        if disagree:
            flags.append('точки хранят legacy kind (цвета живой карты): ' +
                         ', '.join(disagree) + '; kind сущности — метка для радара')
    ent = OrderedDict()
    ent['id'] = unique_id(slugify(name))
    ent['name'] = name
    ent['name_normalized'] = norm_name(name)
    addr = pts[0]['address'] if pts else src_rows[0]['address']
    ent['address_normalized'] = norm_addr(addr)
    ent['kind'] = kind
    ent['kind_source'] = ksrc
    if flags:
        ent['kind_review'] = flags
    ent['points'] = [OrderedDict(p) for p in pts]
    ent['csv_rows'] = [OrderedDict(r) for r in src_rows]
    ent['source'] = source
    murls = [r['mathex_url'] for r in src_rows if r.get('mathex_url')]
    if murls:
        ent['mathex_url'] = murls[0]
    entities.append(ent)

# place-only сущности; точки с associated_school, указывающим на другую place-only
# группу, присоединяются к той сущности (MCS Polyanka -> MCS School / Magic Castle School)
merge_target = {}
for g in place_only_groups:
    pts = [p for p in places if place_group[p['id']] == g]
    assoc = {p.get('associated_school') for p in pts if p.get('associated_school')}
    if len(assoc) == 1:
        tgt = assoc.pop()
        if tgt != g and tgt in place_only_groups:
            merge_target[g] = tgt

for g in place_only_groups:
    if g in merge_target:
        continue  # точки уйдут к целевой сущности
    pts = [p for p in places if place_group[p['id']] == g]
    pts += [p for src, tgt in merge_target.items() if tgt == g
            for p in places if place_group[p['id']] == src]
    name = g
    trow = table.get(name)
    a1 = admission_positive(trow.get('admission')) if trow else None
    r2 = hardcode_hits(name, BLUE_LEGACY)
    allkg = all(p['entity'] == 'kindergarten' for p in pts)
    flags = []
    if allkg:
        kind, ksrc = 'green', f'kindergarten program (places.json {SNAP})'
    elif a1:
        kind = 'blue'
        ksrc = f'rule:content-admission ({name} in schools_content.table {SNAP})'
    elif r2:
        kind = 'blue'
        ksrc = f'rule:legacy-build_data.py BLUE\\GREEN ({", ".join(r2)})'
    else:
        kind = 'red'
        ksrc = 'default: школа из списка (легенда red); сигналов blue нет'
    disagree = sorted({f"{p['id']}={p['kind']}" for p in pts if p['kind'] != kind})
    if disagree and not allkg:
        flags.append('точки хранят legacy kind (цвета живой карты): ' +
                     ', '.join(disagree) + '; kind сущности — метка для радара')
    ent = OrderedDict()
    ent['id'] = unique_id(slugify(name))
    ent['name'] = name
    ent['name_normalized'] = norm_name(name)
    ent['address_normalized'] = norm_addr(pts[0]['address'])
    ent['kind'] = kind
    ent['kind_source'] = ksrc
    if flags:
        ent['kind_review'] = flags
    ent['points'] = [OrderedDict(p) for p in pts]
    ent['csv_rows'] = []
    ent['source'] = 'map-only'
    entities.append(ent)

canon = OrderedDict()
canon['_meta'] = OrderedDict([
    ('description', 'Канонический реестр школ/садов schools-map-mathex. Источник истины; '
                    'places.json и schools_normalized.csv генерируются build_all.py.'),
    ('created', '2026-09-25'),
    ('snapshot', SNAP),
    ('migration', 'scripts/migrate_to_entities.py'),
    ('counts', {'entities': len(entities), 'csv_rows': sum(len(e['csv_rows']) for e in entities),
                'points': sum(len(e['points']) for e in entities)}),
])
canon['place_order'] = [p['id'] for p in places]
canon['csv_order'] = [r['id'] for r in rows]
canon['entities'] = entities

txt = json.dumps(canon, ensure_ascii=False, indent=2) + '\n'
(OUT/'entities.json').write_text(txt, encoding='utf-8')

# ---------- сводка ----------
from collections import Counter
print('entities:', len(entities))
print('csv_rows placed:', sum(len(e['csv_rows']) for e in entities), '/ 69')
print('points placed:', sum(len(e['points']) for e in entities), '/ 45')
print('kinds:', Counter(e['kind'] for e in entities))
print('kinds (entities with csv_rows):', Counter(e['kind'] for e in entities if e['csv_rows']))
print('kind_review flags:', sum(1 for e in entities if e.get('kind_review')))
print('place-only groups:', place_only_groups)
print('mixed groups (часть точек занята):', mixed_groups)
for e in entities:
    if e.get('kind_review'):
        print(f"  REVIEW {e['id'][:44]:44} kind={e['kind']:5} | {' | '.join(e['kind_review'])[:110]}")
