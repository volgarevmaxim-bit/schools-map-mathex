import json,re
from pathlib import Path
ROOT=Path(__file__).parent
# places.json is deliberately the editable data file. This validator makes future changes safe.
data=json.loads((ROOT/'places.json').read_text(encoding='utf-8'))
assert len(data)==43, f'expected 43 objects, got {len(data)}'
ids=[x['id'] for x in data]
assert len(ids)==len(set(ids)), 'duplicate ids'
for x in data:
    assert x['name'] and x['address'] and x['lat'] and x['lon']
    assert x['kind'] in {'green','blue','red'}
print('valid places:',len(data))
print('schools:',sum(x['entity']=='school' for x in data))
print('kindergartens:',sum(x['entity']=='kindergarten' for x in data))
print('colors:',{k:sum(x['kind']==k for x in data) for k in ['green','blue','red']})
# Copy current source documents into the published working tree when present.
for n in ('Лучшие школы Москвы.md','Лучшие детские сады Москвы.md'):
    src=Path.home()/'Downloads'/n
    if src.exists(): (ROOT/n).write_text(src.read_text(encoding='utf-8'),encoding='utf-8')
    else: print('warning: missing',n)
info=ROOT/'Schools_Session_Summary.md'
print('summary:',info.exists())
    