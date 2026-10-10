# -*- coding: utf-8 -*-
"""Геокодинг адресов через Яндекс Геокодер.

Читает audit/addresses/to_geocode.json, заполняет lat/lon в merge_plan.json
(по refs = id новых точек). Очередность: transport-20 школ → portal blue → остальные.
Идемпотентно: адреса с уже проставленными координатами пропускаются.

Яндекс API: https://geocode-maps.yandex.ru/1.x/
Пейсинг: 0.7 сек между запросами. Прогресс-сейв каждые 50 успешных.
"""
import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request

AUDIT = r"C:\Users\volga\schools-map-mathex\audit\addresses"
PLAN_PATH = os.path.join(AUDIT, "merge_plan.json")
GEO_PATH = os.path.join(AUDIT, "to_geocode.json")
NOTFOUND_PATH = os.path.join(AUDIT, "yandex_notfound.json")
ENV_PATH = r"C:\Users\volga\school-transport\.env"
SCHOOLS_CSV = r"C:\Users\volga\school-transport\config\schools.csv"

# читаем ключ из .env
YANDEX_KEY = None
with open(ENV_PATH, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("YANDEX_GEOCODER_KEY="):
            YANDEX_KEY = line.split("=", 1)[1].strip()
            break
assert YANDEX_KEY, f"YANDEX_GEOCODER_KEY не найден в {ENV_PATH}"


def norm_addr(s):
    s = str(s or "").lower()
    s = re.sub(r"(?:г\.?\s*)?москва,?\s*", "", s)
    return re.sub(r"[^а-яa-z0-9]", "", s)


def geocode_yandex(address):
    """Выполнить запрос к Яндекс Геокодеру. Возвращает (lat, lon) или None."""
    params = urllib.parse.urlencode({
        "apikey": YANDEX_KEY,
        "format": "json",
        "geocode": address,
        "lang": "ru_RU",
        "results": "1",
    })
    url = f"https://geocode-maps.yandex.ru/1.x/?{params}"

    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                data = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            status = e.code
            data = e.read().decode("utf-8", errors="replace") if e.fp else "{}"
        except urllib.error.URLError as e:
            return None, f"URLError: {e.reason}"

        if status == 200:
            r = json.loads(data)
            fm = r.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
            if fm:
                pos = fm[0]["GeoObject"]["Point"]["pos"]  # "lon lat"
                parts = pos.split()
                return (float(parts[1]), float(parts[0])), None
            else:
                return None, None  # notfound
        elif status in (403, 429):
            return None, f"STOP {status}"  # фатально
        elif status == 400:
            return None, None  # notfound
        else:
            if attempt == 1:
                time.sleep(3)
                continue
            return None, f"HTTP {status}"

    return None, f"HTTP {status}"


def main():
    plan = json.loads(open(PLAN_PATH, "r", encoding="utf-8").read())
    todo = json.loads(open(GEO_PATH, "r", encoding="utf-8").read())

    # приоритеты: transport-20 → blue → red
    t_ids = set()
    for r in csv.DictReader(open(SCHOOLS_CSV, encoding="utf-8-sig")):
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
    notfound_addrs = []
    hard_stop = False

    for idx, na in enumerate(pending_addrs):
        if hard_stop:
            break

        t = by_addr[na]
        address = t["address"]
        result, err = geocode_yandex(address)

        if result is None and err and err.startswith("STOP"):
            print(f"СТОП {err}: {address[:50]}")
            hard_stop = True
            break

        if result is None and err:
            errors += 1
            print(f"ERR {address[:50]}: {err}")
            continue

        if result is None and err is None:
            notfound += 1
            print(f"НЕ НАЙДЕНО: {address[:60]}")
            notfound_addrs.append(address)
            continue

        lat, lon = result
        # заполняем во все new_points по id из refs
        for pid in t["refs"]:
            for sch in plan:
                for np in sch.get("new_points", []):
                    if np["id"] == pid:
                        np["lat"], np["lon"] = lat, lon

        ok += 1

        # прогресс-сейв каждые 50 успешных
        if ok % 50 == 0:
            print(f"  {ok}/{len(pending_addrs)} адресов ok — прогресс-сейв")
            with open(PLAN_PATH, "w", encoding="utf-8") as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)

        if ok % 10 == 0:
            print(f"  {ok} адресов ok, осталось ~{len(pending_addrs) - idx - 1}")

        # пейсинг 0.7 сек
        if idx < len(pending_addrs) - 1 and not hard_stop:
            time.sleep(0.7)

    # финальная запись merge_plan.json
    with open(PLAN_PATH, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    # уменьшить to_geocode.json — только адреса, у которых в плане остались точки с lat is None
    null_addr_norms = set()
    for sch in plan:
        for np in sch.get("new_points", []):
            if np.get("lat") is None:
                null_addr_norms.add(norm_addr(np["address"]))

    todo_rest = [t for t in todo if norm_addr(t["address"]) in null_addr_norms]

    with open(GEO_PATH, "w", encoding="utf-8") as f:
        json.dump(todo_rest, f, ensure_ascii=False, indent=2)

    # сохранить ненайденные
    if notfound_addrs:
        with open(NOTFOUND_PATH, "w", encoding="utf-8") as f:
            json.dump(notfound_addrs, f, ensure_ascii=False, indent=2)
    else:
        # если пусто — удалить файл или записать пустой список
        if os.path.exists(NOTFOUND_PATH):
            os.remove(NOTFOUND_PATH)

    rem = sum(1 for sch in plan for np in sch.get("new_points", []) if np.get("lat") is None)
    print(f"\nитог: ok={ok}, errors={errors}, notfound={notfound}")
    print(f"осталось точек без координат: {rem}")
    print(f"осталось записей в to_geocode.json: {len(todo_rest)}")


if __name__ == "__main__":
    main()