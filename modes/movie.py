#!/usr/bin/env python3
"""Kino/film uchun rejim: ingliz tilidagi videoni o'zbekcha dublyajga o'tkazish.

`modes/course.py` bilan deyarli bir xil. Yagona farq — 1-bosqich:

    course.py : steps/remove_audio  — audio oqimi butunlay tashlab yuboriladi
    movie.py  : steps/remove_vocals — faqat odam nutqi olib tashlanadi (demucs)

Kinoda orqa fondagi musiqa, effektlar va tabiat tovushlari ahamiyatli, shuning
uchun ular saqlanib qoladi va 7-bosqichda o'zbekcha nutq ostiga qo'shiladi.

Bosqichlar ketma-ketligi:
    1. steps/remove_vocals   — videodan odam nutqini olib tashlash (demucs + ffmpeg)
    2. steps/extract_audio   — ASL videodan audio ajratib olish (ffmpeg)
    3. steps/generate_srt    — audiodan .srt transkripsiya (openai-whisper)
    4. steps/translate_srt   — .srt ni tarjima qilish (LLM — rejada)
    5. steps/normalize_srt   — matnlarni TTS uchun normalize qilish (uztts)
    6. steps/generate_audios — tarjimadagi matnlarni audioga o'girish (Navoiy TTS)
    7. steps/merge_audios    — audiolarni videoga timestamp bo'yicha biriktirish (ffmpeg)

Diqqat: 2-bosqich transkripsiya uchun ASL videodan audio oladi (nutq o'sha yerda),
7-bosqich esa 1-bosqichda tayyorlangan nutqsiz videoni ishlatadi. O'sha videoda
fon ovozi qolgani uchun u ham aralashmaga tushadi — balandligini
`steps/merge_audios.py` dagi `ORIGINAL_VOLUME` bilan boshqarasiz.

1-bosqich sekin ishlaydi (demucs). Apple Silicon'da tezlashtirish uchun:
    DEMUCS_DEVICE=mps python modes/movie.py

Ishga tushirish (loyiha ildizidan):
    python modes/movie.py
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.extract_audio import extract_audio  # noqa: E402
from steps.generate_audios import generate_audios  # noqa: E402
from steps.generate_srt import generate_srt  # noqa: E402
from steps.merge_audios import merge_audios  # noqa: E402
from steps.normalize_srt import normalize_srt  # noqa: E402
from steps.remove_vocals import OUTPUT_SUFFIX, remove_vocals  # noqa: E402
from steps.translate_srt import translate_srt  # noqa: E402
from utils.common import ask_path, fail, format_duration  # noqa: E402

SRC_LANGUAGE = "en"
DST_LANGUAGE = "uz"


def main() -> None:
    print("=" * 60)
    print(" Kino tarjimon: ingliz -> o'zbek (fon ovozi saqlanadi)")
    print("=" * 60)

    if shutil.which("ffmpeg") is None:
        fail("ffmpeg topilmadi. Uni o'rnating: brew install ffmpeg")

    video_path = ask_path(
        "Video fayl manzilini kiriting (/path/to/movie/movie.mp4)", must_exist=True
    )

    # Vaqt savollardan keyin o'lchanadi — foydalanuvchi o'ylab turgan vaqt
    # bosqichlarning davomiyligiga qo'shilib ketmasligi uchun.
    started_at = time.monotonic()

    # Barcha oraliq fayllar video bilan yonma-yon joylashadi.
    audio_path = video_path.with_suffix(".wav")
    srt_path = video_path.with_suffix(".srt")
    translated_srt_path = video_path.with_name(f"{video_path.stem}-{DST_LANGUAGE}.srt")
    normalized_srt_path = video_path.with_name(f"{video_path.stem}-{DST_LANGUAGE}-normalized.srt")
    audios_dir = video_path.parent / "audios"
    background_video = video_path.with_name(f"{video_path.stem}{OUTPUT_SUFFIX}{video_path.suffix}")
    output_path = video_path.with_name(f"{video_path.stem}-{DST_LANGUAGE}{video_path.suffix}")

    print("\n[1/7] Videodan odam nutqi olib tashlanmoqda (fon ovozi qoladi)...")
    background_video = remove_vocals(video_path, background_video)
    print(f"  Tayyor: {background_video}")

    # Transkripsiya uchun ASL video kerak — nutq faqat o'sha yerda.
    print("\n[2/7] Videodan audio ajratilmoqda...")
    audio_path = extract_audio(video_path, audio_path)
    print(f"  Tayyor: {audio_path}")

    print("\n[3/7] Audiodan .srt generatsiya qilinmoqda...")
    srt_path = generate_srt(audio_path, srt_path, src_language=SRC_LANGUAGE)
    print(f"  Tayyor: {srt_path}")

    print(f"\n[4/7] .srt {SRC_LANGUAGE} -> {DST_LANGUAGE} tarjima qilinmoqda...")
    translated_srt_path = translate_srt(
        srt_path, translated_srt_path, src_language=SRC_LANGUAGE, dst_language=DST_LANGUAGE
    )
    print(f"  Tayyor: {translated_srt_path}")

    print("\n[5/7] Matnlar TTS uchun normalize qilinmoqda...")
    normalized_srt_path = normalize_srt(translated_srt_path, normalized_srt_path)
    print(f"  Tayyor: {normalized_srt_path}")

    print("\n[6/7] Tarjima matnlari audioga o'girilmoqda...")
    audios_dir = generate_audios(normalized_srt_path, audios_dir)
    print(f"  Tayyor: {audios_dir}")

    print("\n[7/7] Audiolar videoga biriktirilmoqda...")
    output_path = merge_audios(background_video, audios_dir, output_path)

    print("\n" + "=" * 60)
    print(f" Tayyor! Natija: {output_path}")
    print(f" Umumiy vaqt: {format_duration(time.monotonic() - started_at, full=True)}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
