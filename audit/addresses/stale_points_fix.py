# -*- coding: utf-8 -*-
"""Решение владельца 12.10: чистка устаревших базовых точек + ВШЭ b4.

Правило владельца: если связь адреса со школой не подтверждается источниками —
точку удалять; если подтверждается, но нет информации о role — оставлять
с role=None.

УДАЛЯЕМЫЕ (связь не подтверждается источниками):
  сунц-мгу:         «Проектируемый 5186-й проезд» — адрес не существует
  1529:             «Обыденский переулок, 9» — неточная форма 2-го Обыденского 9 (дубль b2)
  технологии:       «6-й Можайский переулок» — не в офиц. списке (Резервный 10, Красноармейская 15)
  интеграция XXI:   «Катукова 16к1» — офиц. 16к3 и 1-й Волоколамский 9к2
  1534:             «Кедрова 18к3» — не среди офиц. корпусов (переезд на Кедрова 11)
  548:              «Ереванская 33» — старый, не используемый адрес
  171:              «Фрунзенская 10» — неверен (единственный корпус 2-я Фрунзенская 7А)
  ЦПМ:              «Олимпийский 11с1» — закрыт (переезд 2026)

ОСТАВЛЯЕМ с role=None (связь подтверждается):
  интеллектуал:     «Кременчугская 11с4» — фактический адрес школы (int.mskobr.ru)
  лицей-ниу-вшэ:    «Б. Харитоньевский 4с1» — учебный корпус (владелец: «не учебный» было ошибкой)

ВШЭ b4: адрес «3-й Колобовский пер., 8, стр. 2» -> «8, стр. 3» — учебный корпус
(владелец: «Колобовский 8с3 — 2 направления»; live school.hse.ru/allocation:
«3-й Колобовский переулок, д. 8, стр.3»; 8с2 — администрация).

Идемпотентно. Запускать из audit/addresses/.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # schools-map-mathex
CANON = ROOT / "data" / "entities.json"
CONTENT = ROOT / "schools_content.json"

DELETE_POINTS = {
    "school-сунц-мгу": "Проектируемый 5186-й проезд не существует",
    "school-школа-1529-имени-а-с-грибоедова": "неточная форма 2-го Обыденского пер., 9 (дубль b2)",
    "school-школа-технологии-обучения": "6-й Можайский переулок не в офиц. адресах школы",
    "school-школа-интеграция-xxi-век": "Катукова 16к1 не подтверждается (офиц. 16к3, 1-й Волоколамский 9к2)",
    "school-школа-1534-академическая-школа-1534": "Кедрова 18к3 не среди офиц. корпусов (переезд на Кедрова 11)",
    "school-школа-548-царицыно": "Ереванская 33 — старый неиспользуемый адрес",
    "school-школа-171": "Фрунзенская 10 неверен (единственный корпус — 2-я Фрунзенская 7А)",
    "school-школа-центра-педагогического-мастерства-цпм": "Олимпийский 11с1 закрыт (переезд 2026)",
}

# ВШЭ: b4 — учебный корпус 8с3 (координаты Яндекс-геокодера для 8с3)
VSE_B4 = {
    "address": "Москва, 3-й Колобовский пер., 8, стр. 3",
    "lat": 55.76958,
    "lon": 37.618426,
}
VSE_BASE_SOURCE = ("решение владельца 10.10 (3-я очередь замен): по решению владельца базу сменить; "
                   "из учебных корпусов (school.hse.ru/allocation) Лялин 3А — 4 направления. "
                   "Уточнение 12.10: «Харитоньевский 4 — не учебный корпус» признано ошибкой; "
                   "база = любой учебный корпус, оставлена Лялин 3А; учебный корпус на Колобовском — 8с3 (не 8с2)")


def main():
    canon = json.loads(CANON.read_text(encoding="utf-8"))
    content = json.loads(CONTENT.read_text(encoding="utf-8"))

    # --- 1) удаление точек из канона ---
    deleted = 0
    for e in canon["entities"]:
        kept = []
        for p in e.get("points", []):
            if p["id"] in DELETE_POINTS:
                print(f"- удаляю {p['id']} | {p.get('address')} | {DELETE_POINTS[p['id']]}")
                deleted += 1
            else:
                kept.append(p)
        e["points"] = kept
    canon["place_order"] = [pid for pid in canon["place_order"] if pid not in DELETE_POINTS]
    canon["_meta"]["counts"]["points"] = len(canon["place_order"])
    canon["_meta"]["counts"]["entities"] = len(canon["entities"])

    # --- 2) ВШЭ: b4 адрес/координаты + источник базы ---
    vse = next(e for e in canon["entities"] if e["id"] == "лицей-ниу-вшэ")
    b4 = next(p for p in vse["points"] if p["id"] == "school-лицей-ниу-вшэ-b4")
    b4["address"] = VSE_B4["address"]
    b4["lat"], b4["lon"] = VSE_B4["lat"], VSE_B4["lon"]
    if vse.get("isochrone_base"):
        vse["isochrone_base"]["source"] = VSE_BASE_SOURCE

    CANON.write_text(json.dumps(canon, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- 3) schools_content.json: убрать спаны удалённых точек, поправить b4 ---
    fixed = 0
    for rec in content["records"]:
        rec["place_ids"] = [p for p in rec.get("place_ids", []) if p not in DELETE_POINTS]
        text = rec.get("place_text", "")
        for pid in DELETE_POINTS:
            if f'<span id="place-{pid}">' not in text:
                continue
            chunks = text.split("<br>")
            kept = [c for c in chunks if f'<span id="place-{pid}">' not in c]
            text = "<br>".join(kept)
            fixed += 1
        if "school-лицей-ниу-вшэ-b4" in rec.get("place_ids", []):
            text = text.replace("3-й Колобовский пер., 8, стр. 2", "3-й Колобовский пер., 8, стр. 3")
            fixed += 1
        rec["place_text"] = text

    CONTENT.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"удалено точек из канона: {deleted}, правок content: {fixed}")
    print(f"points в каноне: {len(canon['place_order'])}")


if __name__ == "__main__":
    main()
