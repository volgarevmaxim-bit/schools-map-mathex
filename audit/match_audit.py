# -*- coding: utf-8 -*-
"""A2: match-отчёт schools_normalized.csv (69) <-> places.json (45). Read-only.
Метод: нормализация + fuzzy (SequenceMatcher: plain + token_sort) + haversine.
Verdict: match / unsure / no_match. Жадное 1:1 по убыванию combined.
"""
import csv, json, re, math
from difflib import SequenceMatcher
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
CALIBRATE = '--calibrate' in __import__('sys').argv

STOP_NAME = {'гбоу', 'ано', 'по', 'чоу', 'им', 'имени', 'г.', 'гор.'}
def norm_name(s):
    s = (s or '').lower().replace('ё', 'е')
    s = re.sub(r'[«»"\'\(\)\[\].,!?—–-]', ' ', s)
    s = s.replace('№', ' no ')
    s = re.sub(r'\bшкола[\s-]+пансион\b', ' ', s)
    toks = [t for t in s.split() if t and t not in STOP_NAME]
    return ' '.join(toks)

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

def score(a, b, norm):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    plain = SequenceMatcher(None, na, nb).ratio()
    sa, sb = ' '.join(sorted(na.split())), ' '.join(sorted(nb.split()))
    tsort = SequenceMatcher(None, sa, sb).ratio()
    base = max(plain, tsort)
    # containment: короткое имя целиком внутри длинного ("Летово" ⊂ "Школа-пансион Летово…")
    ta, tb = set(na.split()), set(nb.split())
    if ta and tb and (ta <= tb or tb <= ta):
        base = max(base, 0.72)
    # числовой бонус: номера из имени строки присутствуют в имени точки
    # ("Школа 1533 ЛИТ" → "Лицей №1533 (…) — здание 3–4 классов")
    da = {t for t in ta if t.isdigit()}
    db = {t for t in tb if t.isdigit()}
    if da and da.issubset(db):
        base = max(base, 0.70)
    return round(base, 3)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

rows = list(csv.DictReader(open(ROOT/'schools_normalized.csv', encoding='utf-8')))
places = json.load(open(ROOT/'places.json', encoding='utf-8'))

pairs = []
for r in rows:
    for p in places:
        ns = score(r['name'], p['name'], norm_name)
        as_ = score(r['address'], p['address'], norm_addr)
        d = haversine(float(r['lat']), float(r['lon']), p['lat'], p['lon'])
        geo = 0.20 if d < 300 else (0.10 if d < 800 else 0.0)
        comb = round(ns*0.62 + as_*0.30 + geo, 3)
        pairs.append({'r': r, 'p': p, 'ns': ns, 'as': as_, 'd': d, 'comb': comb})

if CALIBRATE:
    top = sorted(pairs, key=lambda x: -x['comb'])[:60]
    for x in top:
        print(f"comb={x['comb']:.3f} ns={x['ns']:.2f} as={x['as']:.2f} d={int(x['d'])}m | {x['r']['id']} [{x['r']['name'][:40]}] -> {x['p']['id']} [{x['p']['name'][:40]}]")
    __import__('sys').exit(0)

def verdict_of(x):
    ns, as_, d = x['ns'], x['as'], x['d']
    strong_geo = d < 300 and ns >= 0.50
    if (ns >= 0.80 and as_ >= 0.55) or (ns >= 0.62 and as_ >= 0.70) or strong_geo:
        return 'match'
    if (ns >= 0.55 and as_ >= 0.45 and d < 2000) or \
       (ns >= 0.45 and as_ >= 0.60 and d < 5000) or (d < 500 and ns >= 0.45):
        return 'unsure'
    return 'no_match'

def contained(na, nb):
    ta, tb = set(na.split()), set(nb.split())
    return bool(ta and tb and (ta <= tb or tb <= ta))

# --- Проход 1: жадное назначение только сильных match'ей (1:1) ---
pairs.sort(key=lambda x: -x['comb'])
taken_r, taken_p, out = set(), set(), []
for x in pairs:
    rid, pid = x['r']['id'], x['p']['id']
    if rid in taken_r or pid in taken_p:
        continue
    if verdict_of(x) == 'match':
        taken_r.add(rid); taken_p.add(pid)
        out.append({'csv_id': rid, 'csv_name': x['r']['name'], 'csv_address': x['r']['address'],
                    'place_id': pid, 'place_name': x['p']['name'], 'place_kind': x['p']['kind'],
                    'name_score': x['ns'], 'addr_score': x['as'], 'verdict': 'match',
                    'comment': f"combined={x['comb']:.2f}, dist={int(x['d'])}m"})

# CSV-внутренние дубликаты (одна сущность двумя строками) — находить по best-candidate
# без 1:1-ограничения, вердикт от verdict_of; flag в comment.
DUP_PAIRS = [('mathex-skola-cpm', 'forbes-mid-23')]

matched_rows = {o['csv_id'] for o in out}
for r in rows:
    if r['id'] in matched_rows:
        continue
    dup_of = None
    for a, b in DUP_PAIRS:
        if r['id'] == a and b in matched_rows:
            dup_of = b
        elif r['id'] == b and a in matched_rows:
            dup_of = a
    if dup_of:
        best = max((x for x in pairs if x['r']['id'] == r['id']), key=lambda x: x['comb'])
        v = verdict_of(best)
        out.append({'csv_id': r['id'], 'csv_name': r['name'], 'csv_address': r['address'],
                    'place_id': best['p']['id'], 'place_name': best['p']['name'],
                    'place_kind': best['p']['kind'],
                    'name_score': best['ns'], 'addr_score': best['as'], 'verdict': v,
                    'comment': f"CSV duplicate of {dup_of}; best={best['p']['id']} comb={best['comb']:.2f} d={int(best['d'])}m"})
        continue
    cands = [x for x in pairs if x['r']['id'] == r['id'] and x['p']['id'] not in taken_p]
    if not cands:
        out.append({'csv_id': r['id'], 'csv_name': r['name'], 'csv_address': r['address'],
                    'place_id': '', 'place_name': '', 'place_kind': '',
                    'name_score': 0.0, 'addr_score': 0.0, 'verdict': 'no_match',
                    'comment': 'no free candidate places left'})
        continue
    best = max(cands, key=lambda x: x['comb'])
    v = verdict_of(best)
    if v != 'match':  # матч не может появиться тут (проход 1 забрал бы), но на всякий случай
        na, nb = norm_name(r['name']), norm_name(best['p']['name'])
        contained_ = contained(na, nb) and best['ns'] >= 0.62
        # бренд-префикс: первые 2 токена имени совпадают ("Ломоносовская школа …" ↔ "Ломоносовская школа — …")
        brand = len(na.split()[:2]) >= 2 and na.split()[:2] == nb.split()[:2] and best['ns'] >= 0.60
        if contained_ or brand:
            v = 'unsure'  # тот же бренд, другой корпус/кампус — в review-очередь
    if v == 'unsure':
        taken_p.add(best['p']['id'])
        out.append({'csv_id': r['id'], 'csv_name': r['name'], 'csv_address': r['address'],
                    'place_id': best['p']['id'], 'place_name': best['p']['name'],
                    'place_kind': best['p']['kind'],
                    'name_score': best['ns'], 'addr_score': best['as'], 'verdict': 'unsure',
                    'comment': f"same-brand/diff-campus? combined={best['comb']:.2f}, dist={int(best['d'])}m"})
    else:
        out.append({'csv_id': r['id'], 'csv_name': r['name'], 'csv_address': r['address'],
                    'place_id': '', 'place_name': '', 'place_kind': '',
                    'name_score': best['ns'], 'addr_score': best['as'], 'verdict': 'no_match',
                    'comment': f"best: {best['p']['id']} comb={best['comb']:.2f} d={int(best['d'])}m"})

out.sort(key=lambda o: (o['verdict'] != 'match', o['verdict'] != 'unsure', o['csv_id']))
COLS = ['csv_id','csv_name','csv_address','place_id','place_name','place_kind',
        'name_score','addr_score','verdict','comment']
with open(Path(__file__).parent/'match_report.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    w.writerows(out)

print('verdicts:', Counter(o['verdict'] for o in out))
print('matched places by kind:', Counter(o['place_kind'] for o in out if o['verdict'] == 'match'))
matched_p = {o['place_id'] for o in out if o['place_id']}
print(f'places covered: {len(matched_p)}/{len(places)}')
unmatched_places = [p for p in places if p['id'] not in matched_p]
print('unmatched places:')
for p in unmatched_places:
    print(f"  - {p['id']} [{p['name'][:50]}] kind={p['kind']} entity={p['entity']}")
print()
for o in out:
    if o['verdict'] != 'no_match':
        print(f"{o['verdict']:6} ns={o['name_score']:.2f} as={o['addr_score']:.2f} | {o['csv_id']} [{o['csv_name'][:36]}] -> {o['place_id']} [{o['place_name'][:30]}] | {o['comment']}")
