#!/usr/bin/env python3
"""Kokoro TTS: berilgan matnni audio faylga o'giradi.

Ikki xil ishlatiladi:

    # 1) Faylning o'zini ishga tushirganda — matn va manzil input orqali so'raladi
    python utils/kokoro_tts.py

    # 2) Boshqa koddan chaqirganda — argument bilan, hech narsa so'ralmaydi
    from utils.kokoro_tts import text_to_audio
    text_to_audio("Hello world", "assets/hello.wav")

Model birinchi chaqiruvda yuklab olinadi (~350 MB, `~/.cache/huggingface` ga) va
jarayon davomida xotirada saqlanadi — ketma-ket chaqiruvlarda qayta yuklanmaydi.

Environment o'zgaruvchilari:
    KOKORO_LANG   — til kodi (default: a). a/b — amerikacha/britancha ingliz,
                    e — ispan, f — fransuz, h — hind, i — italyan, j — yapon,
                    p — portugal (Braziliya), z — mandarin.
    KOKORO_VOICE  — ovoz nomi (default: af_heart)
    KOKORO_SPEED  — nutq tezligi (default: 1.0)

Diqqat: Kokoro o'zbek tilini QO'LLAB-QUVVATLAMAYDI. O'zbekcha dublyaj uchun
loyihadagi `steps/generate_audios.py` (Navoiy TTS) ishlatiladi.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.common import ask_path, ask_text, fail  # noqa: E402

DEFAULT_LANG = os.environ.get("KOKORO_LANG", "a")
DEFAULT_VOICE = os.environ.get("KOKORO_VOICE", "am_michael")
DEFAULT_SPEED = float(os.environ.get("KOKORO_SPEED", "1.0"))

# Kokoro shu chastotada audio qaytaradi.
SAMPLE_RATE = 24000

# Manzil so'ralganda taklif qilinadigan nom.
DEFAULT_OUTPUT_NAME = "kokoro.wav"

# Bir xil til uchun quvur qayta yaratilmasin — model xotirada qoladi.
_PIPELINES: dict[str, object] = {}


def _pipeline(lang_code: str):
    """KPipeline ni bir marta yaratib, keyingi chaqiruvlarda qayta ishlatish."""
    if lang_code not in _PIPELINES:
        try:
            from kokoro import KPipeline
        except ImportError:
            fail("kokoro topilmadi. O'rnating: pip install kokoro soundfile")

        print(f"  Kokoro modeli yuklanmoqda (til: {lang_code})...")
        _PIPELINES[lang_code] = KPipeline(lang_code=lang_code)
    return _PIPELINES[lang_code]


def text_to_audio(
    text: str | None = None,
    output_path: str | Path | None = None,
    voice: str = DEFAULT_VOICE,
    lang_code: str = DEFAULT_LANG,
    speed: float = DEFAULT_SPEED,
) -> Path:
    """Matnni Kokoro TTS orqali audio faylga o'girish.

    Args:
        text: O'qiladigan matn. Berilmasa (yoki bo'sh bo'lsa), input orqali so'raladi.
        output_path: Natijaviy .wav fayl manzili. Berilmasa, input orqali so'raladi
            (default qiymat: joriy papkadagi `kokoro.wav`).
        voice: Ovoz nomi (default: af_heart).
        lang_code: Til kodi (default: a — amerikacha ingliz).
        speed: Nutq tezligi (1.0 — normal).

    Returns:
        Yaratilgan audio faylning manzili.
    """
    if not text or not text.strip():
        text = ask_text("Matnni kiriting", default="").strip()
        if not text:
            fail("Matn kiritilmadi.")
    text = text.strip()

    if output_path is None:
        output_path = ask_path(
            "Audio fayl qayerga saqlansin",
            default=Path.cwd() / DEFAULT_OUTPUT_NAME,
        )
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    import soundfile
    import torch

    pipeline = _pipeline(lang_code)
    print(f"  Ovoz: {voice} | tezlik: {speed} | matn: {text[:60]!r}")

    chunks = [result.audio for result in pipeline(text, voice=voice, speed=speed)]
    if not chunks:
        fail("Kokoro audio qaytarmadi.")

    # Uzun matn bir nechta bo'lakka bo'linadi — ularni bitta faylga birlashtiramiz.
    audio = torch.cat(chunks) if len(chunks) > 1 else chunks[0]
    soundfile.write(str(output_path), audio.detach().cpu().numpy(), SAMPLE_RATE)

    duration = len(audio) / SAMPLE_RATE
    print(f"  Tayyor: {output_path} ({duration:.1f}s)")
    return output_path


if __name__ == "__main__":
    try:
        text_to_audio()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
