# -*- coding: utf-8 -*-
"""Правка владельца (10.10): Покровский квартал — началка на Б. Трёхсвятительский пер., 4.

Запускать ПОСЛЕ merge_audit.py prepare (prepare пересобирает merge_plan из батчей)
и ПЕРЕД merge_audit.py apply. Ставит building_role='начальная' точке b3
(адрес «Москва, Б. Трёхсвятительский пер., 4», без «с.2»).
"""
import json
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
plan = json.loads((AUDIT / "merge_plan.json").read_text(encoding="utf-8"))

changed = 0
for sch in plan:
    if sch["entity_id"] != "школа-покровский-квартал":
        continue
    for np in sch.get("new_points", []):
        a = str(np.get("address", "")).lower()
        if "трёхсвятительск" in a and "с.2" not in a and "стр" not in a and "с2" not in a.replace(" ", ""):
            if np.get("building_role") != "начальная":
                np["building_role"] = "начальная"
                changed += 1
                print(f"роль → начальная: {np['id']} ({np['address']})")
            else:
                print(f"уже начальная: {np['id']} ({np['address']})")
    break

(AUDIT / "merge_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"изменено точек: {changed}")
