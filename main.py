#!/usr/bin/env python3
"""Ingliz tilidagi videoni o'zbek tilida gapiriladigan variantga o'tkazish.

Bosqichlar ketma-ketligi:
    1. step1_extract_audio  — videodan audio ajratib olish (ffmpeg)
    2. step2_generate_srt   — audiodan .srt transkripsiya (whisper — rejada)
    3. step3_translate_srt  — .srt ni tarjima qilish (LLM — rejada)
    4. step4_generate_audios— tarjimadagi har bir matnni audioga o'girish (TTS — rejada)
    5. step5_merge_audios   — audiolarni videoga timestamp bo'yicha biriktirish (ffmpeg)

Har bir bosqichni alohida ham ishga tushirish mumkin, masalan:
    python step1_extract_audio.py
"""

from __future__ import annotations

import shutil
import sys

from step1_extract_audio import extract_audio
from step2_generate_srt import generate_srt
from step3_translate_srt import translate_srt
from step4_generate_audios import generate_audios
from step5_merge_audios import merge_audios
from utils import ask_path, fail

SRC_LANGUAGE = "en"
DST_LANGUAGE = "uz"


def main() -> None:
    print("=" * 60)
    print(" Video tarjimon: ingliz -> o'zbek (ffmpeg + STT + LLM + TTS)")
    print("=" * 60)

    if shutil.which("ffmpeg") is None:
        fail("ffmpeg topilmadi. Uni o'rnating: brew install ffmpeg")

    video_path = ask_path("Video fayl manzilini kiriting", must_exist=True)

    # Barcha oraliq fayllar video bilan yonma-yon joylashadi.
    audio_path = video_path.with_suffix(".wav")
    srt_path = video_path.with_suffix(".srt")
    translated_srt_path = video_path.with_name(f"{video_path.stem}-{DST_LANGUAGE}.srt")
    audios_dir = video_path.parent / "audios"
    output_path = video_path.with_name(f"{video_path.stem}-{DST_LANGUAGE}{video_path.suffix}")

    print("\n[1/5] Videodan audio ajratilmoqda...")
    audio_path = extract_audio(video_path, audio_path)
    print(f"  Tayyor: {audio_path}")

    print("\n[2/5] Audiodan .srt generatsiya qilinmoqda...")
    srt_path = generate_srt(audio_path, srt_path, language=SRC_LANGUAGE)
    print(f"  Tayyor: {srt_path}")

    print(f"\n[3/5] .srt {SRC_LANGUAGE} -> {DST_LANGUAGE} tarjima qilinmoqda...")
    translated_srt_path = translate_srt(
        srt_path, translated_srt_path, src_language=SRC_LANGUAGE, dst_language=DST_LANGUAGE
    )
    print(f"  Tayyor: {translated_srt_path}")

    print("\n[4/5] Tarjima matnlari audioga o'girilmoqda...")
    audios_dir = generate_audios(translated_srt_path, audios_dir)
    print(f"  Tayyor: {audios_dir}")

    print("\n[5/5] Audiolar videoga biriktirilmoqda...")
    output_path = merge_audios(video_path, audios_dir, output_path)

    print("\n" + "=" * 60)
    print(f" Tayyor! Natija: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
