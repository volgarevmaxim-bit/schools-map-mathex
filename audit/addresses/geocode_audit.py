# -*- coding: utf-8 -*-
"""Геокодинг новых корпусов аудита через 2ГИС geocoder (client.py из school-transport).

Читает audit/addresses/to_geocode.json, заполняет lat/lon в merge_plan.json
(по refs = id новых точек). Очередность: transport-20 школ → portal blue → остальные.
Бюджет: 45/день (50−5 резерв, счётчик client.py). QuotaExhaustedError → сохраняем
частично. Идемпотентно: адреса с уже проставленными координатами пропускаются.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent    # schools-map-mathex (скрипт в audit/addresses/)
AUDIT = ROOT / "audit" / "addresses"
sys.path.insert(0, str(Path(r"C:\Users\volga\school-transport\src")))
from client import geocode, QuotaExhaustedError  # noqa: E402

PLAN_PATH = AUDIT / "merge_plan.json"
GEO_PATH = AUDIT / "to_geocode.json"


def norm_addr(s):
    s = str(s or "").lower()
    s = re.sub(r"(?:г\.?\s*)?москва,?\s*", "", s)
    return re.sub(r"[^а-яa-z0-9]", "", s)


def main():
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    todo = json.loads(GEO_PATH.read_text(encoding="utf-8"))

    # приоритеты: transport-20 → blue → red
    t_ids = set()
    import csv
    for r in csv.DictReader(open(r"C:\Users\volga\school-transport\config\schools.csv",
                                 encoding="utf-8-sig")):
        if r["selected"] == "1":
            t_ids.add(r["entity_id"])
    def school_prio(sch):
        if sch["entity_id"] in t_ids:
            return 0
        return 1 if sch["kind"] == "blue" else 2
    prio = {sch["name"]: (school_prio(sch), sch["entity_id"]) for sch in plan}
    by_addr = {norm_addr(t["address"]): t for t in todo}

    # какие адреса уже проставлены в плане
    done = set()
    for sch in plan:
        for np in sch.get("new_points", []):
            if np.get("lat") is not None and np.get("lon") is not None:
                done.add(norm_addr(np["address"]))
    pending_addrs = [a for a in by_addr if a not in done]
    plan_schools = {sch["entity_id"]: sch for sch in plan}

    # порядок адресов по приоритету школ (refs → school)
    addr_school = {}
    for sch in plan:
        for np in sch.get("new_points", []):
            addr_school[norm_addr(np["address"])] = sch["entity_id"]
    pending_addrs.sort(key=lambda a: prio[plan_schools[addr_school[a]]["name"]] if a in addr_school else (9, ""))

    print(f"на геокодинг: {len(pending_addrs)} адресов (свежих), уже готово: {len(done)}")
    ok, errors, notfound = 0, 0, 0
    try:
        for na in pending_addrs:
            t = by_addr[na]
            r = geocode(t["address"], fields="items.point,items.name")
            if r["status"] != 200:
                errors += 1
                print(f"ERR {t['address'][:50]}: статус {r['status']}")
                continue
            items = (r["data"] or {}).get("result", {}).get("items", []) if isinstance(r["data"], dict) else []
            if not items or "point" not in items[0]:
                notfound += 1
                print(f"НЕ НАЙДЕНО: {t['address'][:60]}")
                continue
            lat, lon = items[0]["point"]["lat"], items[0]["point"]["lon"]
            for pid in t["refs"]:
                for sch in plan:
                    for np in sch.get("new_points", []):
                        if np["id"] == pid:
                            np["lat"], np["lon"] = lat, lon
            ok += 1
            if ok % 10 == 0:
                print(f"  {ok} адресов ok")
    except QuotaExhaustedError as e:
        print("СТОП по лимиту:", e)

    PLAN_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    todo_rest = [t for t in todo if norm_addr(t["address"]) in
                 {norm_addr(np["address"]) for sch in plan for np in sch["new_points"]
                  if np.get("lat") is None}]
    GEO_PATH.write_text(json.dumps(todo_rest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"итог: ok={ok}, ошибок={errors}, не найдено={notfound}")
    rem = sum(1 for sch in plan for np in sch["new_points"] if np.get("lat") is None)
    print(f"осталось точек без координат: {rem}")


if __name__ == "__main__":
    main()
