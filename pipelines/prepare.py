#!/usr/bin/env python3
"""Tarjimadan oldingi tayyorgarlik: faqat 1-3 bosqichlarni ketma-ket bajaradi.

    1. steps/remove_audio   — videodan audio qismini olib tashlash (ffmpeg)
    2. steps/extract_audio  — ASL videodan audio ajratib olish (ffmpeg)
    3. steps/generate_srt   — audiodan .srt transkripsiya (openai-whisper)

Farqi: BARCHA savollar boshida, bir marta so'raladi. Bosqichlar boshlangandan
keyin dastur hech narsa so'ramaydi — hamma qiymat funksiyalarga argument sifatida
uzatiladi, shuning uchun ular ichkarida input kutmaydi.

Eslatma: 2-bosqich transkripsiya uchun ASL videodan audio oladi (nutq faqat
o'sha yerda), 1-bosqich esa ovozsiz nusxani tayyorlaydi.

Ishga tushirish (loyiha ildizidan):
    python pipelines/prepare.py

Bir nechta video uchun: batches/prepare_batch.py
"""

from __future__ import annotations

import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.extract_audio import extract_audio  # noqa: E402
from steps.generate_srt import DEFAULT_SRC_LANGUAGE, generate_srt  # noqa: E402
from steps.remove_audio import OUTPUT_SUFFIX, remove_audio  # noqa: E402
from utils.common import ask_path, ask_text, ask_yes_no, fail, format_duration  # noqa: E402


@dataclass
class Answers:
    """Boshida yig'ib olinadigan barcha qiymatlar."""

    video_path: Path
    silent_video: Path
    audio_path: Path
    srt_path: Path
    src_language: str
    redo_srt: bool  # .srt mavjud bo'lsa, qayta generatsiya qilinsinmi


def collect_answers() -> Answers:
    """Barcha savollarni bir joyda, bosqichlar boshlanishidan oldin so'rash."""
    video_path = ask_path(
        "Video fayl manzilini kiriting (/path/to/docker/docker.mp4)", must_exist=True
    )

    silent_video = ask_path(
        "1) Ovozsiz video qayerga saqlansin",
        default=video_path.with_name(f"{video_path.stem}{OUTPUT_SUFFIX}{video_path.suffix}"),
    )
    audio_path = ask_path(
        "2) Transkripsiya uchun audio qayerga saqlansin",
        default=video_path.with_suffix(".wav"),
    )
    srt_path = ask_path(
        "3) Transkripsiya .srt fayli qayerga saqlansin",
        default=video_path.with_suffix(".srt"),
    )
    # Raqamlar — savol tartibi (bosqich raqami emas), shuning uchun til savoli 4).
    src_language = ask_text(
        "4) Audiodagi nutq tili (auto — o'zi aniqlaydi)", default=DEFAULT_SRC_LANGUAGE
    )

    # Tayyor .srt uchun savol ham SHU YERDA beriladi, aks holda bosqich
    # o'rtasida so'ralib qolardi. (1- va 2-bosqichlar tez ishlaydi — ular
    # so'ramasdan qayta bajariladi.)
    redo_srt = True
    if is_ready(srt_path):
        redo_srt = ask_yes_no(
            f"   {srt_path.name} allaqachon mavjud. Qaytadan generatsiya qilinsinmi?", default=False
        )

    return Answers(
        video_path=video_path,
        silent_video=silent_video,
        audio_path=audio_path,
        srt_path=srt_path,
        src_language=src_language,
        redo_srt=redo_srt,
    )


def is_ready(path: Path) -> bool:
    """Fayl mavjud va bo'sh emasmi."""
    return path.is_file() and path.stat().st_size > 0


def run(answers: Answers) -> None:
    """Bosqichlarni ketma-ket bajarish — bu yerdan keyin savol berilmaydi."""
    print("\n[1/3] Videodan audio olib tashlanmoqda...")
    remove_audio(answers.video_path, answers.silent_video)
    print(f"  Tayyor: {answers.silent_video}")

    print("\n[2/3] Videodan audio ajratilmoqda...")
    extract_audio(answers.video_path, answers.audio_path)
    print(f"  Tayyor: {answers.audio_path}")

    print("\n[3/3] Audiodan .srt generatsiya qilinmoqda...")
    if is_ready(answers.srt_path) and not answers.redo_srt:
        print(f"  Mavjud fayl ishlatildi: {answers.srt_path}")
    else:
        # Fayl turgan bo'lsa, generate_srt ichida "qaytadanmi?" deb so'ralardi —
        # javobni allaqachon olganimiz uchun eskisini olib tashlaymiz.
        answers.srt_path.unlink(missing_ok=True)
        generate_srt(answers.audio_path, answers.srt_path, src_language=answers.src_language)
        print(f"  Tayyor: {answers.srt_path}")


def main() -> None:
    print("=" * 60)
    print(" Tayyorgarlik: 1-3 bosqichlar (ovozsiz video + transkripsiya)")
    print("=" * 60)

    if shutil.which("ffmpeg") is None:
        fail("ffmpeg topilmadi. Uni o'rnating: brew install ffmpeg")

    answers = collect_answers()

    print("\n" + "-" * 60)
    print(" Savollar tugadi. Bosqichlar boshlanmoqda...")
    print("-" * 60)

    # Vaqt savollardan keyin o'lchanadi — javob kutilgan vaqt hisobga olinmaydi.
    started_at = time.monotonic()
    run(answers)
    elapsed = time.monotonic() - started_at

    print("\n" + "=" * 60)
    print(" Tayyor!")
    print(f"   Ovozsiz video : {answers.silent_video}")
    print(f"   Transkripsiya : {answers.srt_path}")
    print(f"   Umumiy vaqt   : {format_duration(elapsed, full=True)}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
