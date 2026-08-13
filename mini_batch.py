#!/usr/bin/env python3
"""Bir nechta video uchun mini.py quvurini (1-3 bosqichlar) ketma-ket bajaradi.

Dastur boshida faqat ikki savol beriladi:

    1. Path       — ichida video papkalari joylashgan ota papka
                    (masalan: /Users/.../assets/docker)
    2. Start      — necha raqamdan boshlansin (masalan 18 -> docker18 dan)

Qolgan hamma qiymat papka nomidan avtomatik aniqlanadi. `docker9` papkasi uchun:

    video_path   : .../docker9/docker9.mp4
    silent_video : .../docker9/docker9-no-audio.mp4
    audio_path   : .../docker9/docker9.wav
    srt_path     : .../docker9/docker9.srt
    src_language : en

Papkalar nomidagi raqam bo'yicha tartiblanadi (docker2 -> docker10 -> docker100),
shuning uchun "start" qiymati aynan o'sha raqamga qaraydi.

Bosqichlar boshlangandan keyin dastur hech narsa so'ramaydi. Bitta video xato
bersa, quvur to'xtamaydi — xato yozib qo'yiladi va keyingi videoga o'tiladi;
oxirida umumiy hisobot chiqadi.
"""

from __future__ import annotations

import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from mini import Answers, is_ready, run
from step1_remove_audio import OUTPUT_SUFFIX
from utils import ask_path, ask_text, fail, format_duration

# Papka ichidagi video shu kengaytmalar bo'yicha qidiriladi (birinchi topilgani olinadi).
VIDEO_SUFFIXES = (".mp4", ".mkv", ".mov", ".webm", ".m4v")

# Papka nomining oxiridagi raqamni ajratib olish: "docker18" -> 18
TRAILING_NUMBER = re.compile(r"(\d+)$")

# Bu papkalar uchun default til (mini.py da har safar so'raladigan qiymat).
SRC_LANGUAGE = "en"


@dataclass
class Job:
    """Bitta papka uchun tayyorlangan ish."""

    folder: Path
    number: int | None
    video_path: Path

    @property
    def name(self) -> str:
        return self.folder.name


def folder_number(folder: Path) -> int | None:
    """Papka nomidagi oxirgi raqam (`docker18` -> 18). Raqam bo'lmasa None."""
    match = TRAILING_NUMBER.search(folder.name)
    return int(match.group(1)) if match else None


def find_video(folder: Path) -> Path | None:
    """Papka nomiga mos video faylni topish: `docker9/docker9.mp4`."""
    for suffix in VIDEO_SUFFIXES:
        candidate = folder / f"{folder.name}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def build_answers(video_path: Path) -> Answers:
    """mini.py kutadigan barcha qiymatlarni video manzilidan hosil qilish."""
    return Answers(
        video_path=video_path,
        silent_video=video_path.with_name(f"{video_path.stem}{OUTPUT_SUFFIX}{video_path.suffix}"),
        audio_path=video_path.with_suffix(".wav"),
        srt_path=video_path.with_suffix(".srt"),
        src_language=SRC_LANGUAGE,
        # Tayyor .srt qayta hisoblanmaydi — batch rejimida savol berilmaydi.
        redo_srt=False,
    )


def collect_jobs(root: Path, start: int | None) -> list[Job]:
    """Ota papka ichidagi ishlarni yig'ib, raqam bo'yicha tartiblash."""
    jobs: list[Job] = []
    skipped: list[str] = []

    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        video_path = find_video(folder)
        if video_path is None:
            skipped.append(f"{folder.name} (ichida {folder.name}.mp4 topilmadi)")
            continue

        number = folder_number(folder)
        if start is not None:
            if number is None:
                skipped.append(f"{folder.name} (nomida raqam yo'q)")
                continue
            if number < start:
                continue

        jobs.append(Job(folder=folder, number=number, video_path=video_path))

    if skipped:
        print(f"\n  E'tiborsiz qoldirilgan papkalar ({len(skipped)} ta):")
        for item in skipped:
            print(f"    - {item}")

    # Raqamli papkalar raqam bo'yicha, raqamsizlari esa oxirida nom bo'yicha.
    jobs.sort(key=lambda job: (job.number is None, job.number or 0, job.name))
    return jobs


def already_done(answers: Answers) -> bool:
    """Uch bosqichning barcha natijalari tayyor bo'lsa, papkani o'tkazib yuboramiz."""
    return all(
        is_ready(path)
        for path in (
            answers.silent_video,
            answers.audio_path,
            answers.srt_path,
        )
    )


def ask_start() -> int | None:
    """Boshlanish raqamini so'rash. Bo'sh Enter — boshidan boshlanadi."""
    while True:
        raw = ask_text("Start (masalan 18 -> docker18 dan boshlanadi)", default="1").strip()
        if raw.lower() in {"", "0", "hammasi", "all"}:
            return None
        if raw.isdigit():
            return int(raw)
        print("  Iltimos butun son kiriting (yoki hammasi uchun 0).")


def main() -> None:
    print("=" * 70)
    print(" Mini batch: bir nechta video uchun 1-3 bosqichlar")
    print("=" * 70)

    if shutil.which("ffmpeg") is None:
        fail("ffmpeg topilmadi. Uni o'rnating: brew install ffmpeg")

    root = ask_path(
        "Path (video papkalari joylashgan ota papka)",
        must_exist=True,
        must_be_dir=True,
    )
    start = ask_start()

    jobs = collect_jobs(root, start)
    if not jobs:
        fail(f"{root} ichidan mos video papkasi topilmadi.")

    print("\n" + "-" * 70)
    print(f" {len(jobs)} ta video topildi: {jobs[0].name} ... {jobs[-1].name}")
    print(f" Til: {SRC_LANGUAGE} | Boshlanish: {start if start is not None else 'boshidan'}")
    print("-" * 70)

    done: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []
    started_at = time.monotonic()

    for index, job in enumerate(jobs, start=1):
        answers = build_answers(job.video_path)

        print("\n" + "=" * 70)
        print(f" [{index}/{len(jobs)}] {job.name}")
        print(f" Video: {job.video_path}")
        print("=" * 70)

        if already_done(answers):
            print("  Barcha natijalar tayyor — o'tkazib yuborildi.")
            skipped.append(job.name)
            continue

        job_started = time.monotonic()
        try:
            run(answers)
        except KeyboardInterrupt:
            raise
        except (Exception, SystemExit) as error:  # noqa: BLE001 — quvur to'xtamasligi kerak
            message = str(error).strip() or error.__class__.__name__
            print(f"\n  [XATO] {job.name}: {message}")
            print("  Keyingi videoga o'tilmoqda...")
            failed.append((job.name, message))
            continue

        print(f"\n  {job.name} tayyor ({format_duration(time.monotonic() - job_started)}).")
        done.append(job.name)

    elapsed = time.monotonic() - started_at

    print("\n" + "=" * 70)
    print(" Hisobot")
    print("=" * 70)
    print(f"  Bajarildi          : {len(done)}")
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
