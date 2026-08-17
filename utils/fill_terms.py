#!/usr/bin/env python3
"""Kurs papkasidagi `terms.json` dagi bo'sh o'qilishlarni asosiy lug'atdan to'ldiradi.

Ish tartibi shunday: tarjimadan keyin kurs papkasida `terms.json` yasaladi — unda
matnda inglizcha holida qolgan har bir so'z kalit, qiymati esa bo'sh string:

    { "container": "", "container'lar": "", "Docker'ni": "" }

Bu skript loyiha ildizidagi asosiy `terms.json` (ilgari aniqlangan o'qilishlar
to'plami) asosida o'sha bo'sh qiymatlarni to'ldiradi:

    { "container": "konteyner", "container'lar": "konteynerlar", "Docker'ni": "Dokerni" }

QOIDA: faqat **birga-bir to'g'ri kelgan** so'zlar to'ldiriladi. So'z asosiy
lug'atda aynan o'zi bo'lishi kerak (katta-kichik harfga qaralmaydi):

    "container"      -> asosiy lug'atda "container" bor    -> to'ldiriladi
    "container."     -> "container." kaliti yo'q           -> not_ready ga
    "container'lar"  -> "container'lar" kaliti yo'q        -> not_ready ga

Ya'ni qo'shimchali va tinish belgili shakllar taxmin qilinmaydi — ularning har
biri asosiy lug'atda alohida kalit bo'lishi kerak.

Ish yakunida kurs papkasida IKKITA fayl qoladi:

    terms.json             — faqat o'qilishi MA'LUM so'zlar
    not_ready_terms.json   — o'qilishi hali noma'lum so'zlar (qiymati bo'sh)

`not_ready_terms.json` dagi so'zlarni qo'lda to'ldirib, skriptni qayta ishga
tushirasiz — o'shalar `terms.json` ga ko'chadi. Hammasining o'qilishi ma'lum
bo'lganda `not_ready_terms.json` o'chiriladi.

Dastur boshida uch narsa so'raladi:

    1. Kurs papkasidagi terms.json
    2. Asosiy terms.json (default: loyiha ildizidagi terms.json)
    3. Allaqachon to'ldirilgan qiymatlar ham yangilansinmi (default: yo'q)

Ishga tushirish (loyiha ildizidan):
    python utils/fill_terms.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from steps.normalize_srt import load_replacements  # noqa: E402
from utils.common import ask_path, ask_yes_no, fail  # noqa: E402

# O'qilishi topilmagan so'zlar shu faylga ajratiladi (terms.json yonida).
NOT_READY_NAME = "not_ready_terms.json"

# O'qilishi topilmagan so'zlar shu faylga ajratiladi (terms.json yonida).
NOT_READY_NAME = "not_ready_terms.json"


def match_case(value: str, sample: str) -> str:
    """Manba so'z bosh harf bilan boshlangan bo'lsa, o'qilishini ham shunday qilish."""
    if sample[:1].isupper() and value[:1].islower():
        return value[:1].upper() + value[1:]
    return value


def reading_for(word: str, main_terms: dict[str, str]) -> str | None:
    """So'zning o'qilishini asosiy lug'atdan olish. Topilmasa None.

    FAQAT birga-bir moslik: so'z asosiy lug'atda aynan o'zi bo'lishi kerak.
    Qo'shimchali ("container'lar") yoki tinish belgili ("container.") shakllar
    taxmin qilinmaydi — ular ham alohida kalit sifatida turishi kerak.
    Katta-kichik harfga qaralmaydi, natijada bosh harf saqlanadi.
    """
    value = main_terms.get(word.strip().lower())
    return match_case(value, word.strip()) if value is not None else None


def fill(
    course_terms: dict[str, str], main_terms: dict[str, str], overwrite: bool
) -> tuple[dict[str, str], dict[str, str], int, int]:
    """Kurs lug'atini to'ldirib, ikkiga ajratish.

    Returns:
        (o'qilishi ma'lum lug'at, o'qilishi noma'lum lug'at,
         to'ldirilganlar soni, tegilmaganlar soni).
    """
    ready: dict[str, str] = {}
    not_ready: dict[str, str] = {}
    added = 0
    kept = 0

    for word, value in course_terms.items():
        # Qo'lda yozilgan qiymat ham "o'qilishi ma'lum" hisoblanadi.
        if value.strip() and not overwrite:
            ready[word] = value
            kept += 1
            continue

        reading = reading_for(word, main_terms)
        if reading is None:
            not_ready[word] = value  # bo'sh yoki eski qiymat o'z holicha qoladi
            continue

        ready[word] = reading
        added += 1

    return ready, not_ready, added, kept


def load_raw(path: Path) -> dict[str, str]:
    """JSON lug'atni kalit tartibi va registri saqlangan holda o'qish."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"JSON o'qilmadi ({path.name}): {error}")
    if not isinstance(data, dict):
        fail(f"{path.name}: JSON obyekt (kalit-qiymat) bo'lishi kerak.")
    return {str(key): str(value) for key, value in data.items()}


def main() -> None:
    print("=" * 70)
    print(" Kurs lug'atini asosiy terms.json asosida to'ldirish")
    print("=" * 70)

    course_path = ask_path(
        "Kurs papkasidagi terms.json manzili",
        must_exist=True,
    )
    main_path = ask_path(
        "Asosiy terms.json manzili",
        default=ROOT / "terms.json",
        must_exist=True,
    )
    if main_path == course_path:
        fail("Asosiy va kurs lug'ati bir xil fayl bo'lishi mumkin emas.")

    overwrite = ask_yes_no(
        "Allaqachon to'ldirilgan qiymatlar ham yangilansinmi?", default=False
    )

    course_terms = load_raw(course_path)
    not_ready_path = course_path.with_name(NOT_READY_NAME)

    # Oldingi ishga tushirishdan qolgan not_ready_terms.json ni ham qo'shib olamiz:
    # foydalanuvchi u yerda qo'lda to'ldirgan bo'lsa, o'sha so'z terms.json ga qaytadi.
    if not_ready_path.is_file():
        for word, value in load_raw(not_ready_path).items():
            if not course_terms.get(word, "").strip():
                course_terms[word] = value

    if not course_terms:
        fail(f"{course_path.name} bo'sh.")

    # Asosiy lug'at kalitlari kichik harfga o'tkaziladi — moslik registrga qaramaydi.
    main_terms = load_replacements(main_path)
    if not main_terms:
        fail(f"{main_path.name} ichida atama topilmadi.")

    print(f"\n  Kurs lug'ati  : {len(course_terms)} ta so'z")
    print(f"  Asosiy lug'at : {len(main_terms)} ta atama")

    ready, not_ready, added, kept = fill(course_terms, main_terms, overwrite)

    course_path.write_text(
        json.dumps(ready, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not_ready:
        not_ready_path.write_text(
            json.dumps(not_ready, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    else:
        # Hammasining o'qilishi ma'lum — eski fayl qolib ketmasin.
        not_ready_path.unlink(missing_ok=True)

    print("\n" + "=" * 70)
    print(" Hisobot")
    print("=" * 70)
    print(f"  To'ldirildi          : {added}")
    print(f"  Tegilmadi (tayyor)   : {kept}")
    print(f"  O'qilishi ma'lum     : {len(ready)}  -> {course_path.name}")
    print(f"  O'qilishi noma'lum   : {len(not_ready)}"
          + (f"  -> {not_ready_path.name}" if not_ready else "  (fayl yaratilmadi)"))
    print(f"  Papka                : {course_path.parent}")

    if not_ready:
        print(f"\n  {not_ready_path.name} ichidagilarni qo'lda to'ldirasiz:")
        for word in list(not_ready)[:30]:
            print(f"    {word}")
        if len(not_ready) > 30:
            print(f"    ... va yana {len(not_ready) - 30} ta")
        print(f"\n  To'ldirgach shu skriptni qayta ishga tushiring — ular {course_path.name} ga o'tadi.")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
