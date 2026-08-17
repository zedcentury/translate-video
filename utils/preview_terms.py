#!/usr/bin/env python3
"""Atamalarning o'qilishini tekshirish uchun sinov audiolarini generatsiya qiladi.

`terms.json` dagi o'qilish to'g'rimi yoki yo'qmi — buni faqat quloq bilan aniqlash
mumkin. Shuning uchun skript har bir atamani gap ichiga qo'yib, TTS orqali o'qitadi:

    "container": "konteyner"   ->   container.wav : "Endi konteyner sahifasiga kiring"

Fayl nomi KALIT so'z bilan (`container.wav`), gapdagi matn esa uning O'QILISHI
bilan bo'ladi. Shunday qilib fayllarni tinglab chiqib, qaysi atama noto'g'ri
o'qilayotganini darrov topasiz.

Dastur boshida uch narsa so'raladi:

    1. terms.json manzili — o'qilishlar shu fayldan olinadi
    2. Audiolar qaysi papkaga saqlansin
       (default: terms.json yonidagi `terms_audios`)
    3. Qaysi so'z — bitta kalit so'z kiritilsa, faqat o'shaning audiosi
       yasaladi. Bo'sh qoldirilsa (Enter), fayldagi BARCHA atamalar olinadi.

Audio fayli allaqachon mavjud bo'lsa, u O'TKAZIB YUBORILADI — ustiga yozilmaydi.
Qaytadan yasash uchun eski faylni o'chiring.

TTS sozlamalari `steps/generate_audios.py` dagidek environment orqali beriladi:
NAVOIY_REFERENCE, NAVOIY_EMOTION, NAVOIY_SPEED, NAVOIY_SEED.

Ishga tushirish (loyiha ildizidan):
    python utils/preview_terms.py
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.generate_audios import NavoiyTTS  # noqa: E402
from steps.normalize_srt import load_replacements  # noqa: E402
from utils.common import (  # noqa: E402
    ask_path,
    ask_text,
    confirm,
    fail,
    format_duration,
)

# Atama shu gap ichida o'qitiladi. `{word}` o'rniga o'qilishi qo'yiladi.
SENTENCE = "Endi {word} sahifasiga kiring"

# Audiolar shu papkaga (terms.json yonida) saqlanadi.
DEFAULT_DIR_NAME = "terms_audios"

# Shundan ko'p audio bo'lsa, boshlashdan oldin tasdiq so'raladi.
CONFIRM_OVER = 20

# Fayl nomida ishlatib bo'lmaydigan belgilar shu bilan almashtiriladi.
UNSAFE_IN_FILENAME = re.compile(r"[^A-Za-z0-9._'-]+")

# Gapga qo'yishdan oldin o'qilishning chekkasidan olib tashlanadigan belgilar:
# `"container"` -> `container`. Ichkaridagi apostrof (do'ker) tegilmaydi.
EDGE_NOISE = "\"'`«»(){}[],.:;!?—– "


def safe_filename(word: str, used: set[str]) -> str:
    """Atamadan fayl nomi yasash: "docker desktop" -> "docker_desktop.wav".

    Turli atamalar bir xil nomga tushib qolmasligi uchun (`container` va
    `"container`) takrorlanganiga raqam qo'shiladi.
    """
    stem = UNSAFE_IN_FILENAME.sub("_", word).strip("_") or "atama"
    name = f"{stem}.wav"
    counter = 2
    while name.lower() in used:
        name = f"{stem}-{counter}.wav"
        counter += 1
    used.add(name.lower())
    return name


def spoken(reading: str) -> str:
    """O'qilishni gapga qo'yishga tayyorlash: chekka tinish belgilari olinadi."""
    return re.sub(r"\s+", " ", reading.strip(EDGE_NOISE)).strip()


def collect_targets(terms_path: Path, word: str) -> list[tuple[str, str]]:
    """Generatsiya qilinadigan (so'z, o'qilishi) juftliklarini tayyorlash.

    `word` bo'sh bo'lsa — fayldagi barcha atamalar, aks holda faqat o'sha so'z.
    O'qilish har doim `terms.json` dan olinadi.
    """
    terms = load_replacements(terms_path)
    if not terms:
        fail(f"{terms_path.name} ichida atama topilmadi.")

    if word:
        reading = spoken(terms.get(word.lower(), ""))
        if not reading:
            fail(
                f"{word!r} uchun {terms_path.name} da o'qilish topilmadi.\n"
                f'Avval uni faylga qo\'shing: "{word}": "o\'qilishi"'
            )
        # Kalit lug'atdagi ko'rinishida olinadi (kichik harf), aks holda bitta so'z
        # rejimida boshqa nomli fayl yasalib, "mavjud" tekshiruvi ishlamay qolardi.
        return [(word.lower(), reading)]

    targets = [(key, spoken(value)) for key, value in terms.items() if spoken(value)]
    empty = len(terms) - len(targets)
    if empty:
        print(f"  {empty} ta yozuvning o'qilishi bo'sh — ular o'tkazib yuborildi.")
    if not targets:
        fail("O'qilishi yozilgan atama topilmadi.")
    return sorted(targets, key=lambda item: (item[0].lower(), item[0]))


def main() -> None:
    print("=" * 70)
    print(" Atamalar uchun sinov audiolari")
    print("=" * 70)

    terms_path = ask_path(
        "terms.json manzili",
        must_exist=True,
    )
    audios_dir = ask_path(
        "Audiolar qaysi papkaga saqlansin",
        default=terms_path.parent / DEFAULT_DIR_NAME,
    )
    word = ask_text("Qaysi so'z (hammasi uchun Enter)", default="").strip()

    audios_dir.mkdir(parents=True, exist_ok=True)
    targets = collect_targets(terms_path, word)

    # Fayl nomlari oldindan hisoblanadi: mavjudlari o'tkazib yuboriladi.
    used_names: set[str] = set()
    pending: list[tuple[str, Path]] = []
    ready = 0
    for term, reading in targets:
        target_path = audios_dir / safe_filename(term, used_names)
        if target_path.is_file() and target_path.stat().st_size > 0:
            ready += 1
            continue
        pending.append((reading, target_path))

    print(f"\n  {len(targets)} ta atama | {ready} tasi allaqachon tayyor -> {audios_dir}")
    if not pending:
        print("  Barcha audiolar mavjud, TTS o'tkazib yuborildi.")
        return

    print(f"  {len(pending)} ta audio yasaladi. Namuna: {SENTENCE.format(word=pending[0][0])!r}")
    if len(pending) > CONFIRM_OVER:
        confirm("  Bu ancha vaqt oladi. Davom etamizmi?")

    tts = NavoiyTTS()

    started = time.monotonic()
    for position, (reading, target_path) in enumerate(pending, start=1):
        sentence = SENTENCE.format(word=reading)
        print(f"  [{position}/{len(pending)}] {target_path.name} : {sentence}")

        duration = tts.synthesize(sentence, target_path)

        elapsed = time.monotonic() - started
        remaining = (elapsed / position) * (len(pending) - position)
        print(f"      {duration:.1f}s audio | taxminan {format_duration(remaining)} qoldi")

    print("\n" + "=" * 70)
    print(f" Tayyor! {len(pending)} ta yangi audio: {audios_dir}")
    print(f" Umumiy vaqt: {format_duration(time.monotonic() - started, full=True)}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
