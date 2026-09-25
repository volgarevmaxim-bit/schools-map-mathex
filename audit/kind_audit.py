# -*- coding: utf-8 -*-
"""A4: ревизия семантики kind — places.json vs GREEN/BLUE-хардкоды build_data.py."""
import json, re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT/'build_data.py').read_text(encoding='utf-8')
green_set = eval(re.search(r'GREEN\s*=\s*(\{.*?\})', src, re.S).group(1))
blue_set = eval(re.search(r'BLUE\s*=\s*(\{.*?\})', src, re.S).group(1))
print(f'GREEN hardcoded: {len(green_set)} names')
print(f'BLUE hardcoded: {len(blue_set)} names')
print(f'BLUE \\ GREEN (дали blue в старом пайплайне): {sorted(blue_set - green_set)}')
print(f'GREEN \\ BLUE: {sorted(green_set - blue_set)}')

places = json.load(open(ROOT/'places.json', encoding='utf-8'))
print('\nplaces kind counts:', Counter(p['kind'] for p in places))
print('places entity counts:', Counter(p['entity'] for p in places))
print('unique group values:', len({p['group'] for p in places}))

# Как бы build_data.py классифицировал текущие точки (если бы запускался сейчас)
aliases = {'Школа Президент':'Президент','Школа Wunderpark International School':'Wunderpark International School','Школа 1514':'Школа 1514'}
def old_category(name):
    n = aliases.get(name, name)
    return 'green' if n in green_set else ('blue' if n in blue_set else 'red')

print('\n=== Расхождения меток: places.json vs build_data.py (если бы запускался сейчас) ===')
diffs = 0
for p in places:
    old = old_category(p['name'])
    if old != p['kind']:
        diffs += 1
        print(f"  {p['id'][:52]:52} | places={p['kind']:5} | build_data={old:5} | имя: {p['name'][:45]}")
print(f'всего расхождений: {diffs} из {len(places)}')

print('\n=== 3 blue-объекта карты: сверка с BLUE-хардкодом ===')
for p in places:
    if p['kind'] == 'blue':
        in_blue = aliases.get(p['name'], p['name']) in blue_set
        print(f"  {p['id'][:50]:50} | в BLUE-хардкоде: {in_blue} | {p['name']}")

print('\n=== green-школы (entity=school, kind=green): они же в BLUE? ===')
for p in places:
    if p['entity'] == 'school' and p['kind'] == 'green':
        n = aliases.get(p['name'], p['name'])
        print(f"  {p['name'][:48]:48} | в GREEN: {n in green_set} | в BLUE: {n in blue_set}")

print('\n=== группы точек >1 (материал для A3) ===')
from collections import defaultdict
g = defaultdict(list)
for p in places:
    g[p['group']].append(p)
for grp, ps in sorted(g.items(), key=lambda kv: -len(kv[1])):
    if len(ps) > 1:
        kinds = ','.join(p['kind'] for p in ps)
        ents = ','.join(p['entity'][:4] for p in ps)
        print(f"  {len(ps)}x {grp[:55]:55} | kinds: {kinds} | entities: {ents}")
