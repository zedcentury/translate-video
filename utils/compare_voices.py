#!/usr/bin/env python3
"""Bitta matnni Kokoro'ning barcha erkak ovozlari bilan o'qitib, taqqoslash uchun.

`utils/mixed_tts.py` ni har bir ovoz uchun qayta ishga tushiradi va natijalarni
ovoz nomi bilan saqlaydi:

    voices/am_adam.wav
    voices/am_echo.wav
    ...
    voices/bm_lewis.wav

Fayllarni ketma-ket tinglab, o'zbekcha ovozga (Navoiy TTS) eng yaxshi mos
keladiganini tanlaysiz. So'ng uni `KOKORO_VOICE` orqali doimiy qilib qo'yasiz.

Matnda inglizcha qismlarni `[start-en]...[end-en]` bilan belgilang — faqat o'sha
qism ovozdan ovozga o'zgaradi, o'zbekcha qismi hamma faylda bir xil bo'ladi.

Ikki xil ishlatiladi:

    # 1) Faylning o'zini ishga tushirganda — matn va papka input orqali so'raladi
    python utils/compare_voices.py

    # 2) Boshqa koddan chaqirganda — argument bilan
    from utils.compare_voices import compare_voices
    compare_voices("Bugun [start-en]docker[end-en] o'rganamiz.", "voices")

Til kodi ovoz nomidan aniqlanadi: `am_*` -> `a` (amerikacha), `bm_*` -> `b`
(britancha). Mavjud fayllar HAR DOIM qayta yoziladi.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.common import ask_path, ask_text, fail, format_duration  # noqa: E402
from utils.mixed_tts import mixed_text_to_audio  # noqa: E402

# Kokoro'ning inglizcha erkak ovozlari (hexgrad/Kokoro-82M).
VOICES = [
    "am_adam",
    "am_echo",
    "am_eric",
    "am_fenrir",
    "am_liam",
    "am_michael",
    "am_onyx",
    "am_puck",
    "am_santa",
    "bm_daniel",
    "bm_fable",
    "bm_george",
    "bm_lewis",
]

# Manzil so'ralganda taklif qilinadigan papka nomi.
DEFAULT_DIR_NAME = "voices"


def compare_voices(
    text: str | None = None,
    output_dir: str | Path | None = None,
    voices: list[str] | None = None,
) -> list[Path]:
    """Matnni har bir ovoz bilan o'qitib, alohida fayllarga saqlash.

    Args:
        text: O'qiladigan matn. Inglizcha qismlari `[start-en]...[end-en]` bilan
            belgilanadi. Berilmasa (yoki bo'sh bo'lsa), input orqali so'raladi.
        output_dir: Audiolar saqlanadigan papka. Berilmasa, input orqali so'raladi
            (default qiymat: joriy papkadagi `voices`).
        voices: Sinaladigan ovozlar ro'yxati. Berilmasa, `VOICES` olinadi.

    Returns:
        Yaratilgan fayllar ro'yxati.
    """
    if not text or not text.strip():
        text = ask_text("Matnni kiriting", default="").strip()
        if not text:
            fail("Matn kiritilmadi.")

    if output_dir is None:
        output_dir = ask_path(
            "Audiolar qaysi papkaga saqlansin",
            default=Path.cwd() / DEFAULT_DIR_NAME,
        )
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    voices = voices or VOICES
    print(f"\n  {len(voices)} ta ovoz uchun audio yasaladi -> {output_dir}")

    created: list[Path] = []
    failed: list[tuple[str, str]] = []
    started = time.monotonic()

    for position, voice in enumerate(voices, start=1):
        print("\n" + "=" * 70)
        print(f" [{position}/{len(voices)}] {voice}")
        print("=" * 70)

        try:
            path = mixed_text_to_audio(
                text,
                output_dir / f"{voice}.wav",
                voice=voice,
                # Til kodi ovoz nomining birinchi harfidan olinadi: am_* -> a, bm_* -> b.
                lang_code=voice[0],
            )
        except KeyboardInterrupt:
            raise
        except (Exception, SystemExit) as error:  # noqa: BLE001 — bitta ovoz uchun to'xtamaymiz
            message = str(error).strip() or error.__class__.__name__
            print(f"  [XATO] {voice}: {message}")
            failed.append((voice, message))
            continue

        created.append(path)

    print("\n" + "=" * 70)
    print(" Hisobot")
    print("=" * 70)
    print(f"  Yaratildi   : {len(created)}")
    print(f"  Xatolik     : {len(failed)}")
    print(f"  Papka       : {output_dir}")
    if failed:
        for voice, message in failed:
            print(f"    - {voice}: {message}")
    print(f"  Umumiy vaqt : {format_duration(time.monotonic() - started, full=True)}")
    print("=" * 70)
    return created


if __name__ == "__main__":
    try:
        compare_voices()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
