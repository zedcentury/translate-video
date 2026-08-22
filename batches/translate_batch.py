#!/usr/bin/env python3
"""Bir nechta papkadagi .srt fayllarni ketma-ket tarjima qiladi (4-bosqich).

Dastur boshida to'rt narsa so'raladi:

    1. Path       — ichida video papkalari joylashgan ota papka
                    (masalan: /Users/.../assets/docker)
    2. Start      — necha raqamdan boshlansin (masalan 14 -> docker14 dan)
    3. End        — qaysi raqamgacha (masalan 20 -> docker20 ham bajariladi)
    4. Til        — qaysi tildan qaysi tilga (default: en -> uz)

Ichki papkalar nomi ota papka nomidan kelib chiqadi: `docker` -> `docker1`,
`docker2`, ... Har bir papkada `<papka nomi>.srt` fayli qidiriladi:

    /Users/.../assets/docker/docker14/docker14.srt   -> docker14-uz.srt
    /Users/.../assets/docker/docker15/docker15.srt   -> docker15-uz.srt

Tarjima allaqachon mavjud bo'lsa, o'sha papka o'tkazib yuboriladi (qayta
tarjima qilinmaydi — har bir chaqiruv pullik). Bitta fayl xato bersa, quvur
to'xtamaydi; oxirida umumiy hisobot, jami narx va vaqt chiqadi.

Ishga tushirish (loyiha ildizidan):
    python batches/translate_batch.py
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.translate_srt import (  # noqa: E402
    DEFAULT_DST_LANGUAGE,
    DEFAULT_SRC_LANGUAGE,
    EFFORT,
    MODE_LABELS,
    MODEL,
    ask_mode,
    translate_srt_detailed,
)
from utils.common import ask_path, ask_text, fail, format_duration  # noqa: E402

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


def collect_jobs(root: Path, start: int | None, end: int | None) -> list[Job]:
    """Ota papka ichidagi .srt fayllarni yig'ib, raqam bo'yicha tartiblash.

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

        srt_path = folder / f"{folder.name}.srt"
        if not srt_path.is_file():
            skipped.append(f"{folder.name} (ichida {folder.name}.srt topilmadi)")
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


def ask_languages() -> tuple[str, str]:
    """Qaysi tildan qaysi tilga tarjima qilinishini so'rash."""
    while True:
        src = ask_text("Qaysi tildan (til kodi)", default=DEFAULT_SRC_LANGUAGE).strip().lower()
        dst = ask_text("Qaysi tilga (til kodi)", default=DEFAULT_DST_LANGUAGE).strip().lower()
        if not src or not dst:
            print("  Til kodi bo'sh bo'lmasligi kerak.")
            continue
        if src == dst:
            print("  Manba va tarjima tili bir xil bo'lishi mumkin emas.")
            continue
        return src, dst


def main() -> None:
    print("=" * 70)
    print(" Batch tarjima: bir nechta papkadagi .srt fayllar (4-bosqich)")
    print("=" * 70)

    root = ask_path(
        "Path (video papkalari joylashgan ota papka)",
        must_exist=True,
        must_be_dir=True,
    )
    start = ask_start()
    end = ask_end(start)
    src_language, dst_language = ask_languages()
    # Rejim bir marta so'raladi va barcha fayllarga bir xil qo'llanadi.
    mode = ask_mode()

    jobs = collect_jobs(root, start, end)
    if not jobs:
        fail(f"{root} ichidan mos .srt fayl topilmadi (start={start}, end={end}).")

    oraliq = f"{start if start is not None else 'boshidan'} - {end if end is not None else 'oxirigacha'}"
    print("\n" + "-" * 70)
    print(f" {len(jobs)} ta fayl topildi: {jobs[0].name} ... {jobs[-1].name}")
    print(f" Yo'nalish: {src_language} -> {dst_language} | Oraliq: {oraliq}")
    print(f" Rejim: {mode} — {MODE_LABELS[mode]}")
    print(f" Model: {MODEL} (effort={EFFORT})")
    print("-" * 70)

    done: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []
    total_cost = 0.0
    started_at = time.monotonic()

    for index, job in enumerate(jobs, start=1):
        translated_path = job.srt_path.with_name(f"{job.srt_path.stem}-{dst_language}.srt")

        print("\n" + "=" * 70)
        print(f" [{index}/{len(jobs)}] {job.name}")
        print(f" .srt: {job.srt_path}")
        print("=" * 70)

        job_started = time.monotonic()
        try:
            _path, status, cost = translate_srt_detailed(
                job.srt_path,
                translated_path,
                src_language=src_language,
                dst_language=dst_language,
                # Tayyor tarjima qayta hisoblanmaydi — batch rejimida savol berilmaydi.
                redo=False,
                mode=mode,
            )
        except KeyboardInterrupt:
            raise
        except (Exception, SystemExit) as error:  # noqa: BLE001 — quvur to'xtamasligi kerak
            message = str(error).strip() or error.__class__.__name__
            print(f"\n  [XATO] {job.name}: {message}")
            print("  Keyingi faylga o'tilmoqda...")
            failed.append((job.name, message))
            continue

        total_cost += cost
        if status == "skipped":
            skipped.append(job.name)
        else:
            done.append(job.name)
            print(f"\n  {job.name} tayyor ({format_duration(time.monotonic() - job_started)}).")

    elapsed = time.monotonic() - started_at

    print("\n" + "=" * 70)
    print(" Hisobot")
    print("=" * 70)
    print(f"  Tarjima qilindi    : {len(done)}")
    print(f"  Oldindan tayyor    : {len(skipped)}")
    print(f"  Xatolik bilan      : {len(failed)}")
    print(f"  Jami narx          : ${total_cost:.4f}")
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
