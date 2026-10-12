# -*- coding: utf-8 -*-
"""Правка владельца (12.10): чистка адресов удалённых точек в каноне.

Решения владельца 12.10: у сущностей с удалёнными устаревшими точками поля
`address_normalized` (и `csv_rows` у ЦПМ/Интеграции) всё ещё содержат старые
адреса — править.

Сущности (8 = все с удалёнными точками 12.10):
  - ЦПМ: «олимпийский пр 11с1» (точка Олимпийский 11с1 удалена) + 2 csv-строки
    с адресом Олимпийский 11с1 → база 1-й проезд Марьиной Рощи 3А;
  - Интеграция XXI век: «ул маршала катукова 16к1» (16к1 удалён) + csv-строка
    forbes с 16к1 → база 16к3;
  - 548: «ереванская ул 33» → база Домодедовская 35к2;
  - СУНЦ МГУ: «проектируемый 5186-й проезд» → база Кременчугская 11;
  - 171: «фрунзенская улица, дом 10» → база 2-я Фрунзенская 7А;
  - 1529: «обыденский переулок, дом 9» → база 2-й Обыденский 9;
  - 1534: «академический, улица кедрова, дом 18, корпус 3» (Кедрова 18к3) → Кедрова 11;
  - Технологии обучения: «6-й можайский переулок» → база Резервный проезд 10.

address_normalized = norm_addr(адрес isochrone_base) — нормировка из
scripts/migrate_to_entities.py (скопирована: скрипт не импортобезопасен).
csv_rows: address/lat/lon/description/notes — по базовой точке (b2), источник
(id/source/mathex_url/цена) сохраняется, notes дополняются.

Идемпотентно: старые значения проверяются assert'ом, новые — твёрдый маппинг.
После — python scripts/build_all.py && python scripts/validate.py вручную.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # schools-map-mathex
CANON = ROOT / "data" / "entities.json"


def norm_addr(s):
    s = (s or '').lower().replace('ё', 'е')
    s = re.sub(r'[«»"\'\[\]]', ' ', s)
    for a, b in [('улица', 'ул'), ('проспект', 'пр'), ('переулок', 'пер'), ('шоссе', 'ш'),
                 ('бульвар', 'бул'), ('набережная', 'наб'), ('корпус', 'к'), ('корп.', 'к'),
                 ('строение', 'с'), ('деревня', 'д'), ('город', '')]:
        s = s.replace(a, b)
    s = re.sub(r'[.,]', ' ', s)
    s = re.sub(r'\bмосква\b|\bмосковская область\b', ' ', s)
    s = re.sub(r'(\d)\s*([а-я])\b', r'\1\2', s)
    return ' '.join(t for t in s.split() if t)


# eid -> (старый address_normalized, id базовой точки)
ADDR_FIX = {
    "школа-центра-педагогического-мастерства-цпм": ("олимпийский пр 11с1",
                                                     "school-школа-центра-педагогического-мастерства-цпм-b2"),
    "школа-интеграция-xxi-век": ("ул маршала катукова 16к1",
                                 "school-школа-интеграция-xxi-век-b2"),
    "школа-548-царицыно": ("ереванская ул 33", "school-школа-548-царицыно-b2"),
    "сунц-мгу": ("проектируемый 5186-й проезд", "school-сунц-мгу-b2"),
    "школа-171": ("фрунзенская улица, дом 10", "school-школа-171-b2"),
    "школа-1529-имени-а-с-грибоедова": ("обыденский переулок, дом 9",
                                        "school-школа-1529-имени-а-с-грибоедова-b2"),
    "школа-1534-академическая-школа-1534": ("академический, улица кедрова, дом 18, корпус 3",
                                            "school-школа-1534-академическая-школа-1534-b2"),
    "школа-технологии-обучения": ("6-й можайский переулок", "school-школа-технологии-обучения-b2"),
}

# row_id -> (старый address, старый description-адрес, суффикс notes, eid)
CSV_FIX = {
    "mathex-skola-cpm": ("Олимпийский просп., 11, стр. 1, Москва",
                         "Олимпийский просп., 11, стр. 1, Москва",
                         "; адрес/координаты заменены 12.10 по решению владельца: переезд 2026, "
                         "Олимпийский 11с1 устарел (точка удалена), база — 1-й проезд Марьиной Рощи 3А",
                         "школа-центра-педагогического-мастерства-цпм"),
    "forbes-mid-23": ("Москва, Олимпийский проспект, 11с1",
                      "Москва, Олимпийский проспект, 11с1",
                      "; адрес/координаты заменены 12.10 по решению владельца (Олимпийский 11с1 устарел, "
                      "база — 1-й проезд Марьиной Рощи 3А)",
                      "школа-центра-педагогического-мастерства-цпм"),
    "forbes-high-02": ("Москва, улица Маршала Катукова, 16к1",
                       "Москва, улица Маршала Катукова, 16к1",
                       "; адрес/координаты заменены 12.10 по решению владельца: офиц. 16к3 (точка 16к1 удалена)",
                       "школа-интеграция-xxi-век"),
}

canon = json.loads(CANON.read_text(encoding="utf-8"))
ent_by_id = {e["id"]: e for e in canon["entities"]}

# 1) address_normalized по базе
for eid, (old_an, base_pid) in ADDR_FIX.items():
    ent = ent_by_id[eid]
    assert ent["address_normalized"] == old_an, \
        f"{eid}: address_normalized={ent['address_normalized']!r} != ожидалось {old_an!r}"
    base = next(p for p in ent["points"] if p["id"] == base_pid)
    ib = ent.get("isochrone_base", {})
    assert ib.get("point_id") == base_pid, f"{eid}: isochrone_base.point_id={ib.get('point_id')!r}"
    new_an = norm_addr(ib["address"])
    ent["address_normalized"] = new_an
    print(f"{eid}: address_normalized {old_an!r} -> {new_an!r} (база {base['address']})")

# 2) csv_rows: адрес/координаты/описание по базовой точке
for rid, (old_addr, old_desc_addr, note_suffix, eid) in CSV_FIX.items():
    ent = ent_by_id[eid]
    row = next((r for r in ent["csv_rows"] if r["id"] == rid), None)
    assert row is not None, f"csv-строка {rid} не найдена в {eid}"
    assert row["address"] == old_addr, f"{rid}: address={row['address']!r} != {old_addr!r}"
    assert old_desc_addr in row["description"], f"{rid}: description без {old_desc_addr!r}"
    base = next(p for p in ent["points"] if p["id"] == ent["isochrone_base"]["point_id"])
    row["address"] = base["address"]
    row["lat"], row["lon"] = str(base["lat"]), str(base["lon"])
    row["description"] = row["description"].replace(old_desc_addr, base["address"])
    row["notes"] = (row["notes"] or "") + note_suffix
    print(f"{eid} / {rid}: address -> {base['address']} ({base['lat']}, {base['lon']})")

CANON.write_text(json.dumps(canon, ensure_ascii=False, indent=2), encoding="utf-8")
print("entities.json записан. Далее: python scripts/build_all.py && python scripts/validate.py")
