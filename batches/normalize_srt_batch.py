#!/usr/bin/env python3
"""Bir nechta papkadagi tarjima .srt fayllarini normalize qiladi (5-bosqich).

Dastur boshida so'raladigan qiymatlar:

    1. Path       — ichida video papkalari joylashgan ota papka
                    (masalan: /Users/.../assets/docker)
    2. Start      — necha raqamdan boshlansin (masalan 14 -> docker14 dan)
    3. End        — qaysi raqamgacha (masalan 20 -> docker20 ham bajariladi)
    4. Til        — tarjima tili kodi (default: uz) — `<papka>-uz.srt` shundan topiladi
    5. Atamalar   — umumiy full_terms.json manzili (Enter — almashtirishsiz)
    6. Qayta      — tayyor natijalar qayta hisoblansinmi (default: yo'q)

Ichki papkalar nomi ota papka nomidan kelib chiqadi: `docker` -> `docker1`,
`docker2`, ... Har bir papkada `<papka nomi>-uz.srt` qidiriladi:

    docker14/docker14-uz.srt  ->  docker14/docker14-uz-normalized.srt

Atamalar ro'yxati boshida bir marta so'raladi (`full_terms.json`) va barcha
papkalarga bir xil qo'llanadi. Berilmasa, faqat sonlar/sanalar so'zga
aylantiriladi.

Bosqich bepul va tez (hammasi lokal), lekin bitta fayl xato bersa quvur
to'xtamaydi — oxirida umumiy hisobot chiqadi.

Ishga tushirish (loyiha ildizidan):
    python batches/normalize_srt_batch.py
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.normalize_srt import normalize_srt  # noqa: E402
from steps.translate_srt import DEFAULT_DST_LANGUAGE  # noqa: E402
from utils.common import (  # noqa: E402
    ask_optional_path,
    ask_path,
    ask_text,
    ask_yes_no,
    fail,
    format_duration,
)

# Papka nomining oxiridagi raqamni ajratib olish: "docker18" -> 18
TRAILING_NUMBER = re.compile(r"(\d+)$")


@dataclass
class Job:
    """Bitta papka uchun tayyorlangan ish."""

    folder: Path
    number: int | None
    srt_path: Path

    @property
    def name(self) -> str:
        return self.folder.name


def folder_number(folder: Path) -> int | None:
    """Papka nomidagi oxirgi raqam (`docker18` -> 18). Raqam bo'lmasa None."""
    match = TRAILING_NUMBER.search(folder.name)
    return int(match.group(1)) if match else None


def collect_jobs(
    root: Path, start: int | None, end: int | None, dst_language: str
) -> list[Job]:
    """Ota papka ichidagi tarjima .srt fayllarni yig'ib, raqam bo'yicha tartiblash.

    Faqat nomi ota papka nomi bilan boshlanadigan papkalar olinadi
    (`docker` -> `docker1`, `docker2`, ...). `start` va `end` chegaralari
    ikkalasi ham ichiga oladi.
    """
    prefix = root.name
    jobs: list[Job] = []
    skipped: list[str] = []

    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        if not folder.name.startswith(prefix):
            skipped.append(f"{folder.name} (nomi '{prefix}' bilan boshlanmaydi)")
            continue

        srt_path = folder / f"{folder.name}-{dst_language}.srt"
        if not srt_path.is_file():
            skipped.append(f"{folder.name} (ichida {srt_path.name} topilmadi)")
            continue

        number = folder_number(folder)
        if start is not None or end is not None:
            if number is None:
                skipped.append(f"{folder.name} (nomida raqam yo'q)")
                continue
            if start is not None and number < start:
                continue
            if end is not None and number > end:
                continue

        jobs.append(Job(folder=folder, number=number, srt_path=srt_path))

    if skipped:
        print(f"\n  E'tiborsiz qoldirilgan papkalar ({len(skipped)} ta):")
        for item in skipped:
            print(f"    - {item}")

    # Raqamli papkalar raqam bo'yicha, raqamsizlari esa oxirida nom bo'yicha.
    jobs.sort(key=lambda job: (job.number is None, job.number or 0, job.name))
    return jobs


def ask_start() -> int | None:
    """Boshlanish raqamini so'rash. Bo'sh Enter — boshidan boshlanadi."""
    while True:
        raw = ask_text("Start (masalan 14 -> docker14 dan boshlanadi)", default="1").strip()
        if raw.lower() in {"", "0", "hammasi", "all"}:
            return None
        if raw.isdigit():
            return int(raw)
        print("  Iltimos butun son kiriting (yoki hammasi uchun 0).")


def ask_end(start: int | None) -> int | None:
    """Tugash raqamini so'rash. Bo'sh Enter — oxirigacha davom etadi."""
    while True:
        raw = ask_text("End (masalan 20 -> docker20 gacha, docker20 ham kiradi)", default="oxirigacha")
        raw = raw.strip()
        if raw.lower() in {"", "0", "oxirigacha", "oxiri", "hammasi", "all"}:
            return None
        if not raw.isdigit():
            print("  Iltimos butun son kiriting (yoki oxirigacha uchun Enter).")
            continue

        end = int(raw)
        if start is not None and end < start:
            print(f"  End qiymati Start ({start}) dan kichik bo'lmasligi kerak.")
            continue
        return end


def is_ready(path: Path) -> bool:
    """Fayl mavjud va bo'sh emasmi."""
    return path.is_file() and path.stat().st_size > 0


def main() -> None:
    print("=" * 70)
    print(" Batch normalize: bir nechta papkadagi tarjima .srt fayllari (5-bosqich)")
    print("=" * 70)

    root = ask_path(
        "Path (video papkalari joylashgan ota papka)",
        must_exist=True,
        must_be_dir=True,
    )
    start = ask_start()
    end = ask_end(start)
    dst_language = ask_text("Tarjima tili (til kodi)", default=DEFAULT_DST_LANGUAGE).strip().lower()
    if not dst_language:
        fail("Til kodi bo'sh bo'lmasligi kerak.")

    common_terms = ask_optional_path(
        f"Umumiy atamalar JSON fayli ({root / 'full_terms.json'})"
    )
    redo = ask_yes_no("Tayyor natijalar qayta hisoblansinmi?", default=False)

    jobs = collect_jobs(root, start, end, dst_language)
    if not jobs:
        fail(f"{root} ichidan mos -{dst_language}.srt fayl topilmadi (start={start}, end={end}).")

    oraliq = f"{start if start is not None else 'boshidan'} - {end if end is not None else 'oxirigacha'}"
    print("\n" + "-" * 70)
    print(f" {len(jobs)} ta fayl topildi: {jobs[0].name} ... {jobs[-1].name}")
    print(f" Til: {dst_language} | Oraliq: {oraliq}")
    print(f" Umumiy atamalar: {common_terms if common_terms else 'berilmadi'}")
    print("-" * 70)

    done: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []
    started_at = time.monotonic()

    for index, job in enumerate(jobs, start=1):
        output_path = job.srt_path.with_name(f"{job.srt_path.stem}-normalized.srt")

        print("\n" + "=" * 70)
        print(f" [{index}/{len(jobs)}] {job.name}")
        print(f" .srt: {job.srt_path}")
        print("=" * 70)

        if is_ready(output_path) and not redo:
            print(f"  Mavjud fayl ishlatildi: {output_path.name}")
            skipped.append(job.name)
            continue

        try:
            normalize_srt(
                job.srt_path,
                output_path,
                replacements_path=common_terms,
                # Batch rejimida savol berilmasligi kerak: atamalar bo'lmasa,
                # shunchaki almashtirishsiz davom etadi.
                ask_replacements=False,
            )
        except KeyboardInterrupt:
            raise
        except (Exception, SystemExit) as error:  # noqa: BLE001 — quvur to'xtamasligi kerak
            message = str(error).strip() or error.__class__.__name__
            print(f"\n  [XATO] {job.name}: {message}")
            print("  Keyingi faylga o'tilmoqda...")
            failed.append((job.name, message))
            continue

        done.append(job.name)

    elapsed = time.monotonic() - started_at

    print("\n" + "=" * 70)
    print(" Hisobot")
    print("=" * 70)
    print(f"  Normalize qilindi  : {len(done)}")
    print(f"  Oldindan tayyor    : {len(skipped)}")
    print(f"  Xatolik bilan      : {len(failed)}")
    if failed:
        print("\n  Xatoliklar:")
        for name, message in failed:
            print(f"    - {name}: {message}")
    print("-" * 70)
    print(f"  Umumiy vaqt: {format_duration(elapsed, full=True)}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
