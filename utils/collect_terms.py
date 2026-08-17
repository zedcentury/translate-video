#!/usr/bin/env python3
"""terms.json dagi har bir atama uchun matndagi barcha shakllarini yig'ib beradi.

5-bosqichdagi almashtirish faqat ikki tomonida bo'shliq bo'lgan so'zga qo'llaniladi
(`steps/normalize_srt.py`). Shuning uchun `container'lar`, `container.`,
`containerda` kabi shakllar `terms.json` da alohida kalit sifatida turishi
kerak. Bu skript o'sha shakllarni matndan topib, tayyor JSON qilib beradi.

Dastur boshida uch narsa so'raladi:

    1. Path            — ichida video papkalari joylashgan ota papka
                         (masalan: /Users/.../assets/docker)
    2. terms.json      — asosiy atamalar ro'yxati
    3. Natija papkasi  — har bir atama uchun alohida JSON shu yerda yaratiladi

Matn `<papka>/<papka nomi>-uz-normalized.srt` fayllaridan olinadi (5-bosqich
natijasi). Ya'ni allaqachon almashtirilgan so'zlar u yerda yo'q — natijada faqat
HALI QAMRAB OLINMAGAN shakllar to'planadi.

Har bir atama uchun `<natija papkasi>/<atama>.json` yaratiladi:

    container.json
    {
      "container'lar": "konteyner'lar",
      "container.": "konteyner.",
      "containerda": "konteynerda"
    }

Qiymat avtomatik to'ldiriladi: so'z ichidagi atama `terms.json` dagi
o'qilishiga almashtiriladi, qolgan qismi (qo'shimcha, tinish belgisi) o'zgarmaydi.
So'z bir nechta atamani o'z ichiga olsa, eng uzunidan boshlab almashtiriladi.
Bosh harf saqlanadi: `Container'lar` -> `Konteyner'lar`.

Fayllar tayyor bo'lgach, ularni ko'zdan kechirib, kerakli yozuvlarni
`terms.json` ga ko'chirib qo'yasiz.

Ishga tushirish (loyiha ildizidan):
    python utils/collect_terms.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.normalize_srt import load_replacements  # noqa: E402
from utils.common import ask_path, fail  # noqa: E402
from utils.srt import parse_srt  # noqa: E402

# Matn shu ko'rinishdagi fayllardan o'qiladi: docker14/docker14-uz-normalized.srt
SOURCE_SUFFIX = "-uz-normalized.srt"

# Fayl nomida ishlatib bo'lmaydigan belgilar shu bilan almashtiriladi.
UNSAFE_IN_FILENAME = re.compile(r"[^A-Za-z0-9._'-]+")


def collect_tokens(root: Path) -> tuple[Counter[str], int, list[str]]:
    """Papkalardagi .srt matnlaridan bo'shliq bilan ajratilgan so'zlarni yig'ish.

    Returns:
        (so'zlar sanog'i, o'qilgan fayllar soni, manba fayli yo'q papkalar).
    """
    prefix = root.name
    tokens: Counter[str] = Counter()
    files_read = 0
    missing: list[str] = []

    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        if not folder.name.startswith(prefix):
            continue

        source = folder / f"{folder.name}{SOURCE_SUFFIX}"
        if not source.is_file():
            missing.append(folder.name)
            continue

        for cue in parse_srt(source):
            tokens.update(cue.text.split())
        files_read += 1

    return tokens, files_read, missing


def build_reading_pattern(replacements: dict[str, str]) -> re.Pattern[str]:
    """So'z ICHIDAN atamani topadigan regex (bo'shliq talab qilinmaydi).

    Eng uzun atama birinchi tekshiriladi, aks holda "containers" ichidagi
    "container" mos kelib, o'qilishi noto'g'ri yig'ilardi.
    """
    terms = sorted(replacements, key=len, reverse=True)
    return re.compile("|".join(re.escape(term) for term in terms), re.IGNORECASE)


def reading_for(token: str, pattern: re.Pattern[str], replacements: dict[str, str]) -> str:
    """So'z ichidagi atamalarni o'qilishiga almashtirib, to'liq o'qilishni yasash."""

    def substitute(match: re.Match[str]) -> str:
        found = match.group(0)
        value = replacements[found.lower()]
        # Matndagi so'z bosh harf bilan boshlangan bo'lsa, o'qilishi ham shunday bo'lsin.
        if found[:1].isupper() and value[:1].islower():
            value = value[:1].upper() + value[1:]
        return value

    return pattern.sub(substitute, token)


def safe_filename(term: str) -> str:
    """Atamadan fayl nomi yasash: "docker desktop" -> "docker_desktop.json"."""
    name = UNSAFE_IN_FILENAME.sub("_", term).strip("_")
    return f"{name or 'atama'}.json"


def write_term_files(
    tokens: Counter[str], replacements: dict[str, str], output_dir: Path
) -> tuple[int, int, list[tuple[str, int]]]:
    """Har bir atama uchun alohida JSON yozish.

    Returns:
        (yozilgan fayllar soni, jami shakllar soni, [(atama, shakllar soni), ...]).
    """
    pattern = build_reading_pattern(replacements)
    output_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    total_forms = 0
    summary: list[tuple[str, int]] = []

    for term in sorted(replacements):
        forms = {
            token: reading_for(token, pattern, replacements)
            for token in tokens
            if term in token.lower()
        }
        if not forms:
            continue

        ordered = {key: forms[key] for key in sorted(forms, key=lambda s: (s.lower(), s))}
        path = output_dir / safe_filename(term)
        path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        written += 1
        total_forms += len(ordered)
        summary.append((term, len(ordered)))

    return written, total_forms, summary


def main() -> None:
    print("=" * 70)
    print(" Atamalar shakllarini yig'ish (terms.json uchun material)")
    print("=" * 70)

    root = ask_path(
        "Path (video papkalari joylashgan ota papka)",
        must_exist=True,
        must_be_dir=True,
    )
    terms_path = ask_path(
        "terms.json manzili",
        default=root / "terms.json",
        must_exist=True,
    )
    output_dir = ask_path(
        "Natija JSON fayllari qaysi papkaga saqlansin",
        default=root / "terms",
    )

    replacements = load_replacements(terms_path)
    if not replacements:
        fail(f"{terms_path} ichida atama topilmadi.")

    tokens, files_read, missing = collect_tokens(root)
    if not files_read:
        fail(f"{root} ichidan *{SOURCE_SUFFIX} fayllari topilmadi.")

    print(f"\n  {files_read} ta fayl o'qildi, {len(tokens)} ta turli so'z topildi.")
    if missing:
        preview = ", ".join(missing[:5])
        more = f" va yana {len(missing) - 5} ta" if len(missing) > 5 else ""
        print(f"  Manba fayli yo'q papkalar: {len(missing)} ta ({preview}{more})")

    written, total_forms, summary = write_term_files(tokens, replacements, output_dir)

    print("\n" + "=" * 70)
    print(" Hisobot")
    print("=" * 70)
    print(f"  Atamalar (terms.json)     : {len(replacements)}")
    print(f"  JSON yaratildi            : {written}")
    print(f"  Jami shakllar             : {total_forms}")
    print(f"  Papka                     : {output_dir}")

    if summary:
        print("\n  Eng ko'p shaklga ega atamalar:")
        for term, count in sorted(summary, key=lambda item: item[1], reverse=True)[:10]:
            print(f"    {count:5}  {term}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
