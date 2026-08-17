#!/usr/bin/env python3
"""`terms/` papkasidagi JSON'larni va kurs `terms.json` ini bitta faylga birlashtiradi.

`utils/collect_terms.py` har bir atama uchun alohida fayl yasaydi:

    assets/docker/terms/container.json
    assets/docker/terms/image.json
    ...

Ularning ichidagi qo'shimchali shakllarning o'qilishini ko'zdan kechirib,
to'g'rilab chiqqaningizdan keyin shu skript ishga tushiriladi. U barcha
shakllarni kurs `terms.json` idagi atamalar bilan birlashtirib, alifbo
tartibida bitta fayl yasaydi:

    assets/docker/full_terms.json

Birlashtirish tartibi: avval `terms.json`, ustiga `terms/` papkasidagi fayllar
(alifbo bo'yicha) qo'yiladi — ya'ni qo'lda to'g'rilangan shakllar ustun turadi.
Bir xil kalitga turlicha qiymat uchrasa, ekranda ro'yxat qilib ko'rsatiladi.

Qiymati bo'sh yozuvlar natijaga QO'SHILMAYDI: 5-bosqichda ular so'zni matndan
o'chirib yuborardi.

Dastur boshida uch narsa so'raladi:

    1. Path        — kurs papkasi (masalan: assets/docker)
    2. terms/      — shakllar papkasi (default: <kurs papkasi>/terms)
    3. terms.json  — kurs atamalari (default: <kurs papkasi>/terms.json)

Natija har doim kurs papkasida: `full_terms.json`.

Ishga tushirish (loyiha ildizidan):
    python utils/merge_terms.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.common import ask_path, fail  # noqa: E402

# Natija shu nom bilan kurs papkasiga yoziladi.
OUTPUT_NAME = "full_terms.json"


def load_terms(path: Path) -> dict[str, str]:
    """JSON lug'atni kalit registri saqlangan holda o'qish."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"JSON o'qilmadi ({path.name}): {error}")
    if not isinstance(data, dict):
        fail(f"{path.name}: JSON obyekt (kalit-qiymat) bo'lishi kerak.")
    return {str(key): str(value) for key, value in data.items()}


def merge(
    sources: list[tuple[str, dict[str, str]]]
) -> tuple[dict[str, str], list[tuple[str, str, str, str]], int]:
    """Lug'atlarni ketma-ket birlashtirish.

    Args:
        sources: (manba nomi, lug'at) juftliklari — keyingisi oldingisidan ustun.

    Returns:
        (birlashgan lug'at, ziddiyatlar, bo'sh qiymatlar soni).
        Ziddiyat: (so'z, eski qiymat, yangi qiymat, yangi manba).
    """
    merged: dict[str, str] = {}
    origin: dict[str, str] = {}
    conflicts: list[tuple[str, str, str, str]] = []
    empty = 0

    for name, terms in sources:
        for word, value in terms.items():
            value = value.strip()
            if not value:
                # Bo'sh o'qilish foydasiz: normalize bosqichida so'zni o'chirib yuborardi.
                empty += 1
                continue

            previous = merged.get(word)
            if previous is not None and previous != value:
                conflicts.append((word, previous, value, name))
            merged[word] = value
            origin[word] = name

    return merged, conflicts, empty


def main() -> None:
    print("=" * 70)
    print(" Atamalarni birlashtirish -> full_terms.json")
    print("=" * 70)

    root = ask_path(
        "Path (kurs papkasi)",
        must_exist=True,
        must_be_dir=True,
    )
    terms_dir = ask_path(
        "Shakllar papkasi (collect_terms.py natijasi)",
        default=root / "terms",
        must_exist=True,
        must_be_dir=True,
    )
    terms_path = ask_path(
        "Kurs terms.json manzili",
        default=root / "terms.json",
        must_exist=True,
    )

    output_path = root / OUTPUT_NAME
    if output_path in (terms_path, *terms_dir.glob("*.json")):
        fail(f"Natija fayli manbalardan biri bilan bir xil: {output_path}")

    # Avval kurs terms.json, keyin terms/ papkasidagi (qo'lda to'g'rilangan) fayllar.
    sources: list[tuple[str, dict[str, str]]] = [(terms_path.name, load_terms(terms_path))]
    form_files = sorted(terms_dir.glob("*.json"))
    if not form_files:
        fail(f"{terms_dir} ichida .json fayl topilmadi.")
    for path in form_files:
        sources.append((f"terms/{path.name}", load_terms(path)))

    print(f"\n  {terms_path.name}: {len(sources[0][1])} ta yozuv")
    print(f"  {terms_dir.name}/: {len(form_files)} ta fayl, "
          f"{sum(len(terms) for _, terms in sources[1:])} ta yozuv")

    merged, conflicts, empty = merge(sources)
    if not merged:
        fail("Birlashtirish uchun yozuv topilmadi.")

    ordered = {key: merged[key] for key in sorted(merged, key=lambda s: (s.lower(), s))}
    output_path.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print("\n" + "=" * 70)
    print(" Hisobot")
    print("=" * 70)
    print(f"  Jami yozuv         : {len(ordered)}")
    print(f"  Bo'sh (tashlandi)  : {empty}")
    print(f"  Ziddiyat           : {len(conflicts)}")
    print(f"  Natija             : {output_path}")

    if conflicts:
        print("\n  Bir xil so'zga turlicha o'qilish uchradi (oxirgisi olindi):")
        for word, previous, value, name in conflicts[:20]:
            print(f"    {word!r}: {previous!r} -> {value!r}  ({name})")
        if len(conflicts) > 20:
            print(f"    ... va yana {len(conflicts) - 20} ta")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
