#!/usr/bin/env python3
r"""terms.json dagi atamalardan KEYIN kelgan birinchi belgilar ro'yxatini tuzadi.

`steps/normalize_srt.py` dagi almashtirish atamaning o'ng chegarasiga qaraydi:
bo'shliq yoki `TRAILING_CHARS` dagi belgilardan biri turgan bo'lsa, atama
almashtiriladi. Qaysi belgilar o'sha ro'yxatda turishi kerakligini taxmin qilish
o'rniga, shu skript matndan REAL holatni topib beradi.

Dastur boshida ikki narsa so'raladi:

    1. Path        — ichida video papkalari joylashgan ota papka
                     (masalan: /Users/.../assets/docker)
    2. terms.json  — atamalar ro'yxati

Matn FAQAT `<papka>/<papka nomi>-uz.srt` fayllaridan olinadi (`collect_terms.py`
dagi qoidaning o'zi).

QIDIRISH QOIDASI `normalize_srt.py` bilan bir xil: atama chapida bo'shliq bo'lishi
shart (satr boshi ham bo'shliq deb qaraladi), katta-kichik harfga qaralmaydi,
uzun atama qisqasidan oldin sinaladi ("docker compose" -> "docker" emas).
O'ng tomonga esa HECH QANDAY shart qo'yilmaydi — aynan o'sha yerdagi belgi
yig'ilayotgani uchun:

    "container'lar"  -> '
    "container."     -> .
    "containerda"    -> d
    "container bor"  -> bo'shliq

Natija konsolda vergul bilan ajratib chiqadi, eng ko'p uchraganidan boshlab.

Ishga tushirish (loyiha ildizidan):
    python utils/collect_next_chars.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.normalize_srt import load_replacements  # noqa: E402
from utils.collect_terms import SOURCE_SUFFIX  # noqa: E402
from utils.common import ask_path, fail  # noqa: E402
from utils.srt import parse_srt  # noqa: E402

# Bo'shliqni konsolda ko'rish uchun shu belgi bilan ko'rsatamiz.
SPACE_SYMBOL = "␣"

# Har bir belgi uchun jadvalda nechta namuna so'z ko'rsatiladi.
EXAMPLES_PER_CHAR = 3


def read_texts(root: Path) -> tuple[list[str], int, list[str]]:
    """Papkalardagi `-uz.srt` fayllaridan subtitr matnlarini o'qish.

    Returns:
        (matnlar ro'yxati, o'qilgan fayllar soni, manba fayli yo'q papkalar).
    """
    prefix = root.name
    texts: list[str] = []
    files_read = 0
    missing: list[str] = []

    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        if not folder.name.startswith(prefix):
            continue

        source = folder / f"{folder.name}{SOURCE_SUFFIX}"
        if not source.is_file():
            missing.append(folder.name)
            continue

        texts.extend(cue.text for cue in parse_srt(source))
        files_read += 1

    return texts, files_read, missing


def build_pattern(terms: list[str]) -> re.Pattern[str]:
    """Atamani chapida bo'shliq bo'lgan joyda topadigan regex.

    O'ng tomonga shart yo'q — biz aynan o'sha yerdagi belgini o'qimoqchimiz.
    Uzun atama qisqasidan oldin sinalishi uchun uzunligi bo'yicha tartiblaymiz
    (`normalize_srt.build_pattern` dagi sabab).
    """
    ordered = sorted(terms, key=len, reverse=True)
    return re.compile(
        r"(?<= )(?:" + "|".join(re.escape(term) for term in ordered) + r")",
        re.IGNORECASE,
    )


def collect_next_chars(
    texts: list[str], pattern: re.Pattern[str]
) -> tuple[Counter[str], dict[str, list[str]], int]:
    """Har bir atamadan keyingi birinchi belgini sanash.

    Returns:
        (belgilar sanog'i, har bir belgi uchun namuna so'zlar, satr oxiri soni).
    """
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    at_end = 0

    for text in texts:
        # Satr boshi ham bo'shliq deb qaralishi uchun matnni chapdan bo'shliq
        # bilan to'ldiramiz. O'ngga qo'shmaymiz: matn oxiri alohida hisoblanadi.
        padded = f" {text}"
        for match in pattern.finditer(padded):
            if match.end() >= len(padded):
                at_end += 1
                continue

            char = padded[match.end()]
            counts[char] += 1

            # Namuna: atamadan boshlab keyingi bo'shliqqacha bo'lgan so'z.
            bucket = examples.setdefault(char, [])
            if len(bucket) < EXAMPLES_PER_CHAR:
                word = padded[match.start():].split(" ", 1)[0]
                if word not in bucket:
                    bucket.append(word)

    return counts, examples, at_end


def show(char: str) -> str:
    """Belgini konsolda ko'rinadigan qilib berish."""
    if char == " ":
        return SPACE_SYMBOL
    if char == "\t":
        return "\\t"
    return char


def main() -> None:
    print("=" * 70)
    print(" Atamalardan keyingi birinchi belgilar")
    print("=" * 70)

    root = ask_path(
        "1) Path (video papkalari joylashgan ota papka)",
        must_exist=True,
        must_be_dir=True,
    )
    terms_path = ask_path(
        "2) terms.json manzili",
        default=root / "terms.json",
        must_exist=True,
    )

    replacements = load_replacements(terms_path)
    if not replacements:
        fail(f"{terms_path} ichida atama topilmadi.")

    texts, files_read, missing = read_texts(root)
    if not files_read:
        fail(f"{root} ichidan *{SOURCE_SUFFIX} fayllari topilmadi.")

    print(f"\n  {files_read} ta fayl, {len(texts)} ta subtitr o'qildi.")
    if missing:
        preview = ", ".join(missing[:5])
        more = f" va yana {len(missing) - 5} ta" if len(missing) > 5 else ""
        print(f"  Manba fayli yo'q papkalar: {len(missing)} ta ({preview}{more})")

    counts, examples, at_end = collect_next_chars(texts, build_pattern(list(replacements)))
    if not counts:
        fail("Matndan birorta ham atama topilmadi.")

    ordered = [char for char, _ in counts.most_common()]

    print("\n" + "=" * 70)
    print(" Natija")
    print("=" * 70)
    print(f"  Atamalar (terms.json)  : {len(replacements)}")
    print(f"  Topilgan holatlar      : {sum(counts.values())}")
    print(f"  Turli belgilar         : {len(ordered)}")
    if at_end:
        print(f"  Satr oxirida tugagan   : {at_end} (keyin belgi yo'q)")

    print("\n  Belgilar (ko'p uchraganidan kamiga):\n")
    print("    " + ", ".join(show(char) for char in ordered))

    print(f"\n  Batafsil ({SPACE_SYMBOL} = bo'shliq):\n")
    print(f"    {'belgi':<8}{'soni':>8}   namunalar")
    print("    " + "-" * 60)
    for char in ordered:
        sample = ", ".join(examples.get(char, []))
        print(f"    {show(char):<8}{counts[char]:>8}   {sample}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
