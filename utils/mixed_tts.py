#!/usr/bin/env python3
"""Aralash matn (o'zbekcha + inglizcha) uchun ikki TTS'ni birlashtirib audio yasaydi.

Muammo: o'zbekcha matn ichidagi inglizcha atamalarni Navoiy TTS o'zbek o'qish
qoidalari bilan talaffuz qiladi va tushunarsiz chiqadi.

Yechim: matnning inglizcha qismini `[start-en]` va `[end-en]` bilan belgilab
qo'yasiz. Skript matnni bo'laklarga ajratib, har bir bo'lakni o'z dvigateliga
beradi va natijalarni ketma-ket ulaydi:

    o'zbekcha bo'lak  ->  Navoiy TTS   (steps/generate_audios.py)
    inglizcha bo'lak  ->  Kokoro TTS   (utils/kokoro_tts.py)

Misol:

    "Hurmatli o'quvchilar. Bugun [start-en]docker compose[end-en] darsini o'tamiz."

    1. "Hurmatli o'quvchilar. Bugun"  -> o'zbekcha (Navoiy)
    2. "docker compose"               -> inglizcha (Kokoro)
    3. "darsini o'tamiz."             -> o'zbekcha (Navoiy)

Bitta matnda bir nechta inglizcha bo'lak bo'lishi mumkin. Belgi umuman
bo'lmasa, butun matn o'zbekcha deb qaraladi.

Ikki xil ishlatiladi:

    # 1) Faylning o'zini ishga tushirganda — matn va manzil input orqali so'raladi
    python utils/mixed_tts.py

    # 2) Boshqa koddan chaqirganda — argument bilan, hech narsa so'ralmaydi
    from utils.mixed_tts import mixed_text_to_audio
    mixed_text_to_audio("Bugun [start-en]docker[end-en] o'rganamiz.", "dars.wav")

Ikkala dvigatel ham 24 kHz mono qaytargani uchun audiolar qayta kodlanmasdan,
to'g'ridan-to'g'ri ulanadi.

Environment o'zgaruvchilari:
    Navoiy uchun — NAVOIY_REFERENCE, NAVOIY_EMOTION, NAVOIY_SPEED, NAVOIY_SEED
    Kokoro uchun — KOKORO_LANG, KOKORO_VOICE, KOKORO_SPEED
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.common import ask_path, ask_text, fail  # noqa: E402
from utils.kokoro_tts import DEFAULT_LANG, DEFAULT_SPEED, DEFAULT_VOICE, SAMPLE_RATE  # noqa: E402
from utils.kokoro_tts import text_to_audio as kokoro_to_audio  # noqa: E402

# Inglizcha bo'lakni o'rab turadigan belgilar.
START_TAG = "[start-en]"
END_TAG = "[end-en]"

SEGMENT_RE = re.compile(
    re.escape(START_TAG) + r"(.*?)" + re.escape(END_TAG), re.DOTALL | re.IGNORECASE
)

# Yopilmay qolgan belgilarni matndan tozalash uchun.
STRAY_TAG_RE = re.compile(
    re.escape(START_TAG) + "|" + re.escape(END_TAG), re.IGNORECASE
)

# Manzil so'ralganda taklif qilinadigan nom.
DEFAULT_OUTPUT_NAME = "mixed.wav"

# Navoiy modeli bir marta yuklanadi va shu yerda saqlanadi.
_NAVOIY = None


def split_segments(text: str) -> list[tuple[str, str]]:
    """Matnni (til, bo'lak) juftliklariga ajratish.

    Til — "uz" yoki "en". Bo'sh bo'laklar tashlab yuboriladi, yopilmay qolgan
    `[start-en]` kabi belgilar esa matndan olib tashlanadi (aks holda TTS ularni
    ovoz chiqarib o'qib yuborardi).
    """
    segments: list[tuple[str, str]] = []
    position = 0

    for match in SEGMENT_RE.finditer(text):
        before = text[position : match.start()]
        if before.strip():
            segments.append(("uz", _clean(before)))
        if match.group(1).strip():
            segments.append(("en", _clean(match.group(1))))
        position = match.end()

    tail = text[position:]
    if tail.strip():
        segments.append(("uz", _clean(tail)))

    return [(lang, chunk) for lang, chunk in segments if chunk]


def _clean(chunk: str) -> str:
    """Bo'lakdagi ortiqcha bo'shliq va yopilmagan belgilarni tozalash."""
    return re.sub(r"\s+", " ", STRAY_TAG_RE.sub(" ", chunk)).strip()


def _navoiy():
    """Navoiy TTS ni bir marta yuklab, keyingi chaqiruvlarda qayta ishlatish."""
    global _NAVOIY
    if _NAVOIY is None:
        from steps.generate_audios import NavoiyTTS

        _NAVOIY = NavoiyTTS()
    return _NAVOIY


def mixed_text_to_audio(
    text: str | None = None,
    output_path: str | Path | None = None,
    voice: str = DEFAULT_VOICE,
    lang_code: str = DEFAULT_LANG,
    speed: float = DEFAULT_SPEED,
) -> Path:
    """Aralash matnni audio faylga o'girish.

    Args:
        text: O'qiladigan matn. Inglizcha qismlari `[start-en]...[end-en]` bilan
            belgilanadi. Berilmasa (yoki bo'sh bo'lsa), input orqali so'raladi.
        output_path: Natijaviy .wav fayl manzili. Berilmasa, input orqali so'raladi
            (default qiymat: joriy papkadagi `mixed.wav`).
        voice: Kokoro ovozi (inglizcha bo'laklar uchun).
        lang_code: Kokoro til kodi (default: a — amerikacha ingliz).
        speed: Kokoro nutq tezligi.

    Returns:
        Yaratilgan audio faylning manzili.
    """
    if not text or not text.strip():
        text = ask_text("Matnni kiriting", default="").strip()
        if not text:
            fail("Matn kiritilmadi.")

    if output_path is None:
        output_path = ask_path(
            "Audio fayl qayerga saqlansin",
            default=Path.cwd() / DEFAULT_OUTPUT_NAME,
        )
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    segments = split_segments(text)
    if not segments:
        fail("Matn bo'sh — o'qiladigan bo'lak topilmadi.")

    print(f"\n  {len(segments)} ta bo'lak:")
    for position, (lang, chunk) in enumerate(segments, start=1):
        engine = "Kokoro" if lang == "en" else "Navoiy"
        print(f"    {position}. [{lang}] {engine:6} {chunk[:60]!r}")

    import numpy
    import soundfile

    parts: list[numpy.ndarray] = []
    with tempfile.TemporaryDirectory() as workdir:
        for position, (lang, chunk) in enumerate(segments, start=1):
            part_path = Path(workdir) / f"{position:02d}-{lang}.wav"

            if lang == "en":
                kokoro_to_audio(chunk, part_path, voice=voice, lang_code=lang_code, speed=speed)
            else:
                _navoiy().synthesize(chunk, part_path)

            data, rate = soundfile.read(str(part_path), dtype="float32")
            if rate != SAMPLE_RATE:
                fail(f"{part_path.name}: kutilgan {SAMPLE_RATE} Hz o'rniga {rate} Hz keldi.")
            if data.ndim > 1:  # ehtiyot chorasi: stereo bo'lsa, mono ga tushiramiz
                data = data.mean(axis=1)
            parts.append(data)

    audio = numpy.concatenate(parts)
    soundfile.write(str(output_path), audio, SAMPLE_RATE)

    duration = len(audio) / SAMPLE_RATE
    print(f"\n  Tayyor: {output_path} ({duration:.1f}s)")
    return output_path


if __name__ == "__main__":
    try:
        mixed_text_to_audio()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
