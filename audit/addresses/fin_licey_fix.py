# -*- coding: utf-8 -*-
"""Правка владельца (11.10): сущность «Финансовый университет при Правительстве РФ»
→ «Лицей Финансового университета при Правительстве РФ».

Решение владельца (11.10, clarify): переделать сущность в лицей.
Новый базовый адрес — Ленинградский пр-т, 51, стр. 4 (официальный адрес лицея),
второй корпус — Ленинградский пр-т, 49 (учебные классы лицея).
Точка 49/2 (вход вуза) — переадресуется на 49 (49/2 ≈ 49, координаты сохраняются).

Действия:
  1. догеокодинг «Москва, Ленинградский проспект, 51, стр. 4» (Яндекс, ключ из .env);
  2. сущность: name, name_normalized, address_normalized, kind_source;
  3. точки: база -> 51с4 (адрес+координаты+роль старшая); b2 -> 49 (адрес);
  4. schools_content.json: title + place_text (2 спана).
Идемпотентно. После — build_all.py + validate.py вручную.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # schools-map-mathex
sys.path.insert(0, str(Path(__file__).resolve().parent))  # для geocode_yandex
from geocode_yandex import geocode_yandex  # noqa: E402

CANON = ROOT / "data" / "entities.json"
CONTENT = ROOT / "schools_content.json"
EID = "финансовый-университет-при-правительстве-рф"
OLD_NAME = "Финансовый университет при Правительстве РФ"
NEW_NAME = "Лицей Финансового университета при Правительстве РФ"
NEW_BASE_ADDR = "Москва, Ленинградский проспект, 51, стр. 4"
SECOND_ADDR = "Москва, Ленинградский проспект, 49"

# 1) геокодинг нового базового адреса
res, err = geocode_yandex(NEW_BASE_ADDR)
if res is None:
    print(f"!! геокодинг '{NEW_BASE_ADDR}' не удался: {err}")
    sys.exit(1)
lat, lon = res
print(f"геокод {NEW_BASE_ADDR}: {lat}, {lon}")

canon = json.loads(CANON.read_text(encoding="utf-8"))
ent = next(e for e in canon["entities"] if e["id"] == EID)

# 2) сущность
ent["name"] = NEW_NAME
ent["name_normalized"] = re.sub(r"[^а-яa-z0-9 ]", "", NEW_NAME.lower())
ent["address_normalized"] = re.sub(r"[^а-яa-z0-9]", "", NEW_BASE_ADDR.lower())
ent["kind_source"] = ("11.10.26: red — Лицей ФУ (8–11 кл.), набора с 1 класса нет; "
                      "сущность переделана из ВУЗа в лицей по решению владельца (адрес 51с4, корпус 49)")
ent["isochrone_base"] = {
    "point_id": f"school-{EID}",
    "address": NEW_BASE_ADDR,
    "source": "решение владельца 11.10: лицей, офиц. адрес Ленинградский 51с4; корпус 49",
}

# 3) точки
base = next(p for p in ent["points"] if p["id"] == f"school-{EID}")
b2 = next(p for p in ent["points"] if p["id"] == f"school-{EID}-b2")
for p in (base, b2):
    p["name"] = NEW_NAME
    p["group"] = NEW_NAME
base["address"] = NEW_BASE_ADDR
base["lat"], base["lon"] = lat, lon
base["building_role"] = "старшая"
b2["address"] = SECOND_ADDR
b2["building_role"] = "старшая"
print(f"точки: {base['id']} -> {base['address']} ({base['lat']}, {base['lon']})")
print(f"       {b2['id']} -> {b2['address']}")

CANON.write_text(json.dumps(canon, ensure_ascii=False, indent=2), encoding="utf-8")

# 4) schools_content.json
content = json.loads(CONTENT.read_text(encoding="utf-8"))
rec = next((r for r in content["records"]
            if any(pid in r.get("place_ids", []) for pid in (base["id"], b2["id"]))), None)
if rec is None:
    print("!! запись в schools_content.json не найдена")
    sys.exit(1)
rec["title"] = NEW_NAME
rec["place_text"] = (
    f'<span id="place-{base["id"]}"></span>'
    f'<a class="map-link" href="#map" onclick="openOnMap(\'{base["id"]}\');return false;">↑</a> '
    f'<span class="place-label">{NEW_NAME} — старшая школа — {base["address"]}</span><br>'
    f'<span id="place-{b2["id"]}"></span>'
    f'<a class="map-link" href="#map" onclick="openOnMap(\'{b2["id"]}\');return false;">↑</a> '
    f'<span class="place-label">{NEW_NAME} — старшая школа — {b2["address"]}</span>'
)
CONTENT.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
print("schools_content.json: title и place_text обновлены")
print("готово. Далее: python scripts/build_all.py && python scripts/validate.py")
