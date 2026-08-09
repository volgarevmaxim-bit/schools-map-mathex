"""Regenerate the website data after updating the two Markdown source files.
Run: python build_data.py
The verified coordinates/buildings remain in schools.geojson; classifications and prose are editable here/source files.
"""
import json, re
from pathlib import Path
ROOT = Path(__file__).parent
GEO = json.loads((ROOT/'schools.geojson').read_text(encoding='utf-8'))
GREEN = {'Президент','Brookes Moscow','Cambridge International School','Английская школа MCS','Европейская гимназия','Павловская гимназия','Ломоносовская школа','Хорошкола','Новая школа','Золотое сечение','Wunderpark International School'}
BLUE = {'Школа 57','Президент','Brookes Moscow','Cambridge International School','Английская школа MCS','Европейская гимназия','Интеграция XXI век','Школа 1514','Курчатовская школа','Павловская гимназия','Ломоносовская школа','Хорошкола','Новая школа','Золотое сечение','Wunderpark International School'}
def category(name):
    aliases={'Школа Президент':'Президент','Школа Wunderpark International School':'Wunderpark International School','Школа 1514':'Школа 1514'}
    n=aliases.get(name,name)
    return 'green' if n in GREEN else ('blue' if n in BLUE else 'red')
rows=[]; seen={}
for f in GEO['features']:
    name=f['properties']['description'].split('\n')[0]
    ident=re.sub(r'[^a-z0-9]+','-',name.lower()).strip('-'); seen[ident]=seen.get(ident,0)+1
    if seen[ident]>1: ident += '-'+str(seen[ident])
    rows.append({'id':ident,'name':name,'lat':f['geometry']['coordinates'][1],'lon':f['geometry']['coordinates'][0],'kind':category(name),'address':f['properties']['description'].split('\n')[2]})
js=(ROOT/'app.js').read_text(encoding='utf-8'); a=js.index('const PLACES = '); b=js.index(';\nconst COLORS',a)+1
(ROOT/'app.js').write_text(js[:a]+'const PLACES = '+json.dumps(rows,ensure_ascii=False,indent=2)+';'+js[b:],encoding='utf-8')
print('generated',len(rows),'places')
# Update source copies from Downloads when available.
for n in ['Лучшие школы Москвы.md','Лучшие детские сады Москвы.md']:
    src=Path.home()/'Downloads'/n
    if src.exists(): (ROOT/n).write_text(src.read_text(encoding='utf-8'),encoding='utf-8')
print('green/blue/red:', *(sum(x['kind']==k for x in rows) for k in ['green','blue','red']))
