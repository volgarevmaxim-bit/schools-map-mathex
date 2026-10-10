# -*- coding: utf-8 -*-
"""Мерж результатов аудита адресов школ в канон (кросс-задача «Адреса школ»).

Режимы:
  prepare  — читает audit/addresses/batch*_result.json, валидирует, строит
             audit/addresses/merge_plan.json (корпуса → новые точки БЕЗ координат)
             и audit/addresses/to_geocode.json (дедуплицированные адреса).
  apply    — читает merge_plan.json (координаты уже проставлены), вносит в канон:
             entities.json (points + place_order + _meta.counts),
             schools_content.json (place_ids + place_text-спаны),
             затем запускает build_all.py и validate.py. Идемпотентно по id точек.
  transport_csv — генерирует C:\\Users\\volga\\school-transport\\config\\buildings.csv
             (только 20 transport-школ): point_id, school_id, name, address, role,
             lat, lon, is_base. is_base=1 у точки, чьи координаты = schools.csv.

Границы (ТЗ владельца 09.10): базовый адрес transport-школ НЕ меняется без решения
владельца — при несовпадении адреса базовой точки с официальным списком ставится
флаг base_mismatch в merge_plan.json, координаты канона не трогаются.
"""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent    # schools-map-mathex (скрипт в audit/addresses/)
AUDIT = ROOT / "audit" / "addresses"
CANON = ROOT / "data" / "entities.json"
CONTENT = ROOT / "schools_content.json"
TRANSPORT = Path(r"C:\Users\volga\school-transport")

ROLE_LABEL = {
    "старшая": "старшая школа",
    "начальная": "начальная школа",
    "дошкольное": "дошкольное отделение",
    "старшая+начальная": "основное здание",
    "иное": "",
    "неизвестно": "",
}
VALID_ROLES = set(ROLE_LABEL)


def norm_addr(s):
    s = str(s or "").lower().replace("ё", "е")
    s = re.sub(r"(?:г\.?\s*)?москва,?\s*", "", s)
    s = s.replace("пр-т", "проспект").replace("прт", "проспект").replace("б-р", "бульвар")
    s = re.sub(r"д\.\s*|дом\s*", "", s)
    return re.sub(r"[^а-яa-z0-9]", "", s)


STREET_TYPE_WORDS = {
    "улица", "ул", "проспект", "пр", "проезд", "прд", "переулок", "пер",
    "набережная", "наб", "площадь", "пл", "бульвар", "бул", "шоссе", "тракт",
    "тупик", "туп", "аллея", "вал", "просек", "строение", "стр", "дом", "д",
    "домовладение", "владение", "корпус", "корп", "область", "обл", "деревня",
    "дер", "город", "г", "го", "поселок", "поселение", "пос", "район", "рн",
    "им", "литера", "лит", "сооружение", "к", "с",
}


def addr_parts(s):
    """(улица, номер дома '7/10', литера/корпус '4' или '', токены улицы) — мягкое сравнение."""
    s = str(s or "").lower().replace("ё", "е")
    s = re.sub(r"(?:г\.?\s*)?москва,?\s*", "", s)
    s = s.replace("пр-т", "проспект").replace("прт", "проспект").replace("б-р", "бульвар")
    s = s.replace("р-н", "район").replace("г.о.", "го")
    num = ""
    m = re.search(r"(\d+)\s*(?:/\s*(\d+))?", s)
    if m:
        num = m.group(1) + (("/" + m.group(2)) if m.group(2) else "")
    letter = ""
    m2 = re.search(r"\d+\s*[а-яa-z]+(\d+)", s)      # «7с5», «24к4» → литера
    if m2:
        letter = m2.group(1)
    m3 = re.search(r"(?:строение|стр|корпус|корп|литера|лит|сооружение|к|с)\s*\.?\s*(\d+[а-яa-z]?)", s)
    if m3:
        l3 = re.sub(r"[^0-9]", "", m3.group(1))
        if letter and l3 and letter != l3:
            letter = "?"                      # противоречивые литеры — не матчить
        elif not letter:
            letter = l3
    street = re.sub(r"\d+[а-яa-z]*\s*(?:/\s*\d+[а-яa-z]*)?", " ", s)
    has_oblast = "область" in street or "обл" in street
    street = re.sub(r"[^а-яa-z\s]", " ", street)
    tokens = [t for t in street.split() if t and t not in STREET_TYPE_WORDS]
    return "".join(tokens), num, letter, tokens, has_oblast


def addr_match(a, b):
    """True, если адреса — одно здание (улица + номер + литера, типы улиц игнорируются)."""
    sa, na, la, ta, oa = addr_parts(a)
    sb, nb, lb, tb, ob = addr_parts(b)
    if not na or not nb or na != nb:
        return False
    if "?" in (la, lb):
        return False
    if la and lb and la != lb:
        return False
    if not sa or not sb:
        return True
    if sa == sb:
        return True
    shorter = sa if len(sa) <= len(sb) else sb
    if len(shorter) >= 4 and (sa in sb or sb in sa):
        return True
    # областные адреса («д. Борзые, 1» vs «г. Истра, д. Борзые, 1»): совпадение последнего
    # токена улицы при равных номерах
    if (oa and ob) and ta and tb and ta[-1] == tb[-1] and len(ta[-1]) >= 4:
        return True
    return False


def load_canon():
    return json.loads(CANON.read_text(encoding="utf-8"))


def load_batches():
    out = []
    for f in sorted(AUDIT.glob("batch*_result.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append((f.name, d))
        except Exception as e:
            print(f"!! {f.name}: не читается: {e}")
    return out


def entity_by_point(canon, point_id):
    for e in canon["entities"]:
        if any(p["id"] == point_id for p in e.get("points", [])):
            return e
    return None


def match_building(existing_addr, buildings):
    """Сопоставить адрес существующей точки со списком корпусов. (индекс, confidence)."""
    na = norm_addr(existing_addr)
    for i, b in enumerate(buildings):
        if norm_addr(b["address"]) == na:
            return i, 2
        if addr_match(existing_addr, b["address"]):
            return i, 1
    return None, 0


def prepare():
    canon = load_canon()
    batches = load_batches()
    print(f"батчей результатов: {len(batches)}")
    # координаты, уже полученные геокодером в прошлых прогонах, переживают пересборку плана
    coords = {}
    old_plan_path = AUDIT / "merge_plan.json"
    if old_plan_path.exists():
        try:
            old = json.loads(old_plan_path.read_text(encoding="utf-8"))
            for sch in old:
                for np in sch.get("new_points", []):
                    if np.get("lat") is not None and np.get("lon") is not None:
                        coords[np["id"]] = (np["lat"], np["lon"])
        except Exception:
            pass
    if coords:
        print(f"сохранённых координат из прошлого плана: {len(coords)}")
    # группировка строк аудита по СУЩНОСТИ (школы с несколькими точками имеют строку на точку,
    # и агент раскладывал корпуса по строкам неравномерно)
    rows_by_ent, order = {}, []
    n_rows = 0
    for bname, d in batches:
        for s in d.get("schools", []):
            n_rows += 1
            pid = s.get("entity_id")  # в батчах это id ТОЧКИ (places.json)
            ent = entity_by_point(canon, pid)
            if ent is None:
                print(f"!! {s.get('name')}: точка {pid} не найдена в каноне — пропуск")
                continue
            rows_by_ent.setdefault(ent["id"], []).append(s)
            if ent["id"] not in order:
                order.append(ent["id"])
    print(f"строк аудита: {n_rows}, сущностей: {len(order)}")

    plan, to_geocode, addr_seen = [], [], {}
    n_new, n_role_existing = 0, 0
    for eid in order:
        ent = next(e for e in canon["entities"] if e["id"] == eid)
        rows = rows_by_ent[eid]
        buildings = []
        for s in rows:
            for b in s.get("buildings", []):
                addr = re.sub(r"^г\.?\s*", "", str(b.get("address", "")).strip())
                addr = addr.replace("Москва, ", "").replace("москва, ", "").strip()
                buildings.append({
                    "address": f"Москва, {addr}" if not addr.lower().startswith("москва") else addr,
                    "role": b.get("role") if b.get("role") in VALID_ROLES else "неизвестно",
                    "source_url": b.get("source_url", ""),
                    "note": b.get("note", ""),
                })
        if not buildings:
            print(f"!! {ent['name']}: пустой список корпусов — пропуск")
            continue

        # дедуп корпусов по нормализованному адресу (роли склеиваем, «неизвестно» проигрывает)
        deduped = {}
        for b in buildings:
            k = norm_addr(b["address"])
            if k not in deduped:
                deduped[k] = dict(b)
            else:
                r1, r2 = deduped[k]["role"], b["role"]
                if {r1, r2} == {"старшая", "начальная"}:
                    deduped[k]["role"] = "старшая+начальная"
                elif r1 == "неизвестно" and r2 != "неизвестно":
                    deduped[k]["role"] = r2
        buildings = list(deduped.values())

        epts = list(ent.get("points", []))
        flags = []
        used = set()
        matched = {}
        for p in epts:
            j, conf = match_building(p["address"], buildings)
            if j is not None and j not in used:
                used.add(j)
                b = buildings[j]
                role = b["role"] if b["role"] != "неизвестно" else None
                matched[p["id"]] = {"role": role, "address": b["address"], "source_url": b.get("source_url", "")}
                if role and p.get("building_role") != role:
                    p["building_role"] = role
                    n_role_existing += 1
            else:
                flags.append(f"base_mismatch: {p['id']} ({p['address']}) не найден в официальном списке")
        new_points = []
        group = (epts[0].get("group") if epts else None) or ent["name"]
        first_pid = epts[0]["id"]
        k = len(epts)
        for j, b in enumerate(buildings):
            if j in used:
                continue
            k += 1
            npid = f"{first_pid}-b{k}"
            if any(x["id"] == npid for x in canon["entities"] for x in x.get("points", [])):
                print(f"!! {npid} уже в каноне — пропуск добавления")
                continue
            np = {
                "id": npid, "name": ent["name"], "entity": "school", "kind": ent["kind"],
                "address": b["address"], "lat": None, "lon": None, "group": group,
                "building_role": b["role"],
            }
            if npid in coords:
                np["lat"], np["lon"] = coords[npid]
            new_points.append(np)
            na = norm_addr(b["address"])
            if na not in addr_seen:
                addr_seen[na] = {"address": b["address"], "refs": []}
            addr_seen[na]["refs"].append(npid)
            n_new += 1
        notes = "; ".join(filter(None, (r.get("note", "") for r in rows)))
        plan.append({
            "entity_id": ent["id"], "name": ent["name"], "point_id": first_pid,
            "kind": ent["kind"], "source_urls": [b["source_url"] for b in buildings if b.get("source_url")],
            "existing_roles": matched, "new_points": new_points, "flags": flags,
            "audit_discrepancy": any(r.get("discrepancy") for r in rows), "note": notes[:300],
        })

    (AUDIT / "merge_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (AUDIT / "to_geocode.json").write_text(json.dumps(list(addr_seen.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"школ в плане: {len(plan)} | новых точек: {n_new} | ролей у существующих: {n_role_existing}")
    print(f"адресов на геокодинг: {len(addr_seen)}")
    flags_n = sum(len(p["flags"]) for p in plan)
    print(f"флагов base_mismatch: {flags_n}")
    print("следующий шаг: python audit/addresses/geocode_audit.py  (координаты)")
    print("              python audit/addresses/merge_audit.py apply (внесение в канон)")


def apply():
    canon = load_canon()
    plan = json.loads((AUDIT / "merge_plan.json").read_text(encoding="utf-8"))
    content = json.loads(CONTENT.read_text(encoding="utf-8"))

    added_pts, added_roles = 0, 0
    skipped = []
    for sch in plan:
        ent = next((e for e in canon["entities"] if e["id"] == sch["entity_id"]), None)
        if ent is None:
            skipped.append(f"{sch['name']}: сущность не найдена")
            continue
        for pid, info in sch.get("existing_roles", {}).items():
            for p in ent["points"]:
                if p["id"] == pid and info.get("role"):
                    p["building_role"] = info["role"]
        new_ok = []
        for np in sch.get("new_points", []):
            if any(x["id"] == np["id"] for e2 in canon["entities"] for x in e2.get("points", [])):
                continue  # уже внесён (идемпотентно)
            if np.get("lat") is None or np.get("lon") is None:
                skipped.append(f"{np['id']}: нет координат — школа пропущена")
                new_ok = []
                break
            new_ok.append(np)
        if not new_ok:
            continue
        for np in new_ok:
            ent["points"].append(np)
            canon["place_order"].append(np["id"])
            added_pts += 1
        canon["_meta"].setdefault("counts", {})["points"] = len(canon["place_order"])
        canon["_meta"]["counts"]["entities"] = len(canon["entities"])

        # schools_content.json: запись по пересечению place_ids
        rec = next((r for r in content["records"]
                    if any(pid in r.get("place_ids", []) for pid in [p["id"] for p in ent["points"]])), None)
        if rec is None:
            rec = next((r for r in content["records"] if r.get("title") == ent["name"]), None)
        if rec is not None:
            for np in new_ok:
                if np["id"] in rec.setdefault("place_ids", []):
                    continue
                rec["place_ids"].append(np["id"])
                label = ROLE_LABEL.get(np.get("building_role"), "")
                label = f" — {label}" if label else ""
                rec["place_text"] = (rec.get("place_text", "").rstrip() +
                    f'<br><span id="place-{np["id"]}"></span><a class="map-link" href="#map" '
                    f'onclick="openOnMap(\'{np["id"]}\');return false;">↑</a> '
                    f'<span class="place-label">{ent["name"]}{label} — {np["address"]}</span>')
        else:
            skipped.append(f"{ent['name']}: запись в schools_content.json не найдена (place_ids НЕ обновлены)")

    CANON.write_text(json.dumps(canon, ensure_ascii=False, indent=2), encoding="utf-8")
    CONTENT.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"добавлено точек: {added_pts}")
    if skipped:
        print("пропущено:")
        for s in skipped:
            print("  -", s)
    print("пересборка артефактов...")
    r1 = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_all.py")], cwd=ROOT, capture_output=True, text=True)
    print(r1.stdout.strip())
    if r1.returncode:
        print(r1.stderr[-500:])
    r2 = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate.py")], cwd=ROOT, capture_output=True, text=True)
    print(r2.stdout.strip())
    if r2.returncode:
        print(r2.stderr[-500:])


def transport_csv():
    canon = load_canon()
    tsv = TRANSPORT / "config" / "schools.csv"
    t_rows = list(csv.DictReader(open(tsv, encoding="utf-8-sig")))
    t20 = {(r["entity_id"]): (float(r["lat"]), float(r["lon"])) for r in t_rows if r["selected"] == "1"}

    rows = []
    for e in canon["entities"]:
        if e["id"] not in t20:
            continue
        blat, blon = t20[e["id"]]
        for p in e.get("points", []):
            is_base = (round(p.get("lat") or -999, 5) == round(blat, 5)
                       and round(p.get("lon") or -999, 5) == round(blon, 5))
            rows.append({
                "point_id": p["id"], "school_id": e["id"], "name": p["name"],
                "address": p.get("address", ""), "role": p.get("building_role", ""),
                "lat": p.get("lat"), "lon": p.get("lon"), "is_base": 1 if is_base else 0,
            })
    out = TRANSPORT / "config" / "buildings.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["point_id", "school_id", "name", "address",
                                          "role", "lat", "lon", "is_base"])
        w.writeheader()
        w.writerows(rows)
    base = sum(1 for r in rows if r["is_base"])
    print(f"buildings.csv: {len(rows)} строк ({len(t20)} transport-школ), is_base={base}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    {"prepare": prepare, "apply": apply, "transport_csv": transport_csv}[mode]()
