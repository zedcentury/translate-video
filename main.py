#!/usr/bin/env python3
"""Ingliz tilidagi videoni o'zbek tilida gapiriladigan variantga o'tkazish.

Bosqichlar ketma-ketligi:
    1. step1_remove_audio    — videodan audio qismini olib tashlash (ffmpeg)
    2. step2_extract_audio   — ASL videodan audio ajratib olish (ffmpeg)
    3. step3_generate_srt    — audiodan .srt transkripsiya (openai-whisper)
    4. step4_translate_srt   — .srt ni tarjima qilish (LLM — rejada)
    5. step5_normalize_srt   — matnlarni TTS uchun normalize qilish (uztts)
    6. step6_generate_audios — tarjimadagi matnlarni audioga o'girish (Navoiy TTS)
    7. step7_merge_audios    — audiolarni videoga timestamp bo'yicha biriktirish (ffmpeg)

Diqqat: 2-bosqich transkripsiya uchun ASL videodan audio oladi (nutq o'sha yerda),
7-bosqich esa 1-bosqichda tayyorlangan ovozsiz videoni ishlatadi.

Har bir bosqichni alohida ham ishga tushirish mumkin, masalan:
    python step1_remove_audio.py
"""

from __future__ import annotations

import shutil
import sys

from step1_remove_audio import remove_audio
from step2_extract_audio import extract_audio
from step3_generate_srt import generate_srt
from step4_translate_srt import translate_srt
from step5_normalize_srt import normalize_srt
from step6_generate_audios import generate_audios
from step7_merge_audios import merge_audios
from utils import ask_path, fail

SRC_LANGUAGE = "en"
DST_LANGUAGE = "uz"


def main() -> None:
    print("=" * 60)
    print(" Video tarjimon: ingliz -> o'zbek (ffmpeg + STT + LLM + TTS)")
    print("=" * 60)

    if shutil.which("ffmpeg") is None:
        fail("ffmpeg topilmadi. Uni o'rnating: brew install ffmpeg")

    video_path = ask_path(
        "Video fayl manzilini kiriting (/path/to/docker/docker.mp4)", must_exist=True
    )

    # Barcha oraliq fayllar video bilan yonma-yon joylashadi.
    audio_path = video_path.with_suffix(".wav")
    srt_path = video_path.with_suffix(".srt")
    translated_srt_path = video_path.with_name(f"{video_path.stem}-{DST_LANGUAGE}.srt")
    normalized_srt_path = video_path.with_name(f"{video_path.stem}-{DST_LANGUAGE}-normalized.srt")
    audios_dir = video_path.parent / "audios"
    silent_video = video_path.with_name(f"{video_path.stem}-no-audio{video_path.suffix}")
    output_path = video_path.with_name(f"{video_path.stem}-{DST_LANGUAGE}{video_path.suffix}")

    print("\n[1/7] Videodan audio olib tashlanmoqda...")
    silent_video = remove_audio(video_path, silent_video)
    print(f"  Tayyor: {silent_video}")

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
    output_path = merge_audios(silent_video, audios_dir, output_path)

    print("\n" + "=" * 60)
    print(f" Tayyor! Natija: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
