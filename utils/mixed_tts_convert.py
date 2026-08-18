#!/usr/bin/env python3
"""Aralash matn (o'zbekcha + inglizcha) — inglizcha qismi bir xil ovozga o'tkaziladi.

`utils/mixed_tts.py` dan farqi bitta qo'shimcha bosqichda: inglizcha bo'lak
Kokoro bilan o'qilgandan keyin kNN-VC (`utils/voice_convert.py`) orqali namuna
audiodagi ovozga o'tkaziladi. Shundan keyingina bo'laklar birlashtiriladi.

    o'zbekcha bo'lak  ->  Navoiy TTS                      -> xurmo ovozi
    inglizcha bo'lak  ->  Kokoro TTS  ->  kNN-VC          -> xurmo ovozi

Nima uchun kerak: `mixed_tts.py` da o'zbekcha qism Navoiy ovozida (xurmo),
inglizcha qism esa Kokoro ovozida (am_michael) yangraydi — bitta jumla ichida
ikki xil odam gapirayotgandek eshitiladi. Bu yerda inglizcha bo'lakning
TALAFFUZI Kokoro'dan (to'g'ri inglizcha), OVOZI esa namunadan olinadi, natijada
butun audio bitta odamning ovozida chiqadi.

Misol:

    "Bugun [start-en]docker compose[end-en] darsini o'tamiz."

    1. "Bugun"           -> Navoiy               -> xurmo ovozi
    2. "docker compose"  -> Kokoro -> kNN-VC     -> xurmo ovozi
    3. "darsini o'tamiz."-> Navoiy               -> xurmo ovozi

Ikki xil ishlatiladi:

    # 1) Faylning o'zini ishga tushirganda — hamma qiymat input orqali so'raladi
    python utils/mixed_tts_convert.py

    # 2) Boshqa koddan chaqirganda — argument bilan, hech narsa so'ralmaydi
    from utils.mixed_tts_convert import mixed_text_to_converted_audio
    mixed_text_to_converted_audio("Bugun [start-en]docker[end-en] o'rganamiz.", "dars.wav")

Namuna audio ikki joyda ishlatiladi: Navoiy TTS uchun ovoz namunasi sifatida va
kNN-VC uchun "tanlov bazasi" sifatida. Default qiymati Navoiy'ning o'zinikiga
teng (`navoiy-tts/demo/xurmo.wav`), shuning uchun ikkala qism ham bir xil
odamning ovozida chiqadi.

Muhim: kNN-VC sifati namuna audio uzunligiga juda bog'liq. Bir necha soniyalik
namunadan "robotsimon" natija chiqadi — 5-10 daqiqalik yozuv ideal. Shuningdek
kNN-VC 16 kHz da ishlaydi, natija esa 24 kHz ga qaytariladi (o'zbekcha bo'lak
bilan bir xil bo'lishi uchun) — bu inglizcha bo'lakni biroz bo'g'iqroq qiladi.

Environment o'zgaruvchilari:
    Navoiy uchun — NAVOIY_REFERENCE, NAVOIY_EMOTION, NAVOIY_SPEED, NAVOIY_SEED
    Kokoro uchun — KOKORO_LANG, KOKORO_VOICE, KOKORO_SPEED
    kNN-VC uchun — KNNVC_TOPK, KNNVC_DEVICE
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.generate_audios import REFERENCE  # noqa: E402
from utils.common import ask_path, ask_text, fail, format_duration  # noqa: E402
from utils.kokoro_tts import DEFAULT_LANG, DEFAULT_SPEED, DEFAULT_VOICE, SAMPLE_RATE  # noqa: E402
from utils.kokoro_tts import text_to_audio as kokoro_to_audio  # noqa: E402

# Matnni bo'laklarga ajratish mantig'i `mixed_tts.py` da — takrorlamaymiz.
from utils.mixed_tts import split_segments  # noqa: E402
from utils.voice_convert import DEFAULT_TOPK  # noqa: E402
from utils.voice_convert import SAMPLE_RATE as KNNVC_SAMPLE_RATE  # noqa: E402
from utils.voice_convert import load_model, resolve_device  # noqa: E402

# Manzil so'ralganda taklif qilinadigan nom.
DEFAULT_OUTPUT_NAME = "mixed-converted.wav"

# WavLM 20 ms qadam bilan ishlaydi, ya'ni 1 soniya = 50 kadr. Bo'lak shundan
# qisqa bo'lsa, kNN-VC ga yetarli kontekst tushmaydi va natija buziladi.
MIN_FRAMES_WARNING = 25

# Namuna audiodan olingan "tanlov bazasi" — bir marta hisoblanadi.
_MATCHING_SETS: dict[tuple[str, str], object] = {}

# Navoiy modeli ham namuna bo'yicha bir marta yuklanadi.
# (`mixed_tts._navoiy` dan foydalanmaymiz: u namunani argument sifatida
# qabul qilmaydi, `mixed_tts.py` esa o'zgarishsiz qolishi kerak.)
_NAVOIY: dict[str, object] = {}


def _navoiy(reference: Path):
    """Navoiy TTS ni namuna bo'yicha bir marta yuklab, keyin qayta ishlatish."""
    key = str(reference)
    if key not in _NAVOIY:
        from steps.generate_audios import NavoiyTTS

        _NAVOIY[key] = NavoiyTTS(reference=reference)
    return _NAVOIY[key]


def _matching_set(model, reference_path: Path, device: str):
    """Namuna audioning kNN bazasini bir marta hisoblab, keyin qayta ishlatish."""
    key = (str(reference_path), device)
    if key not in _MATCHING_SETS:
        # Manzil MATN ko'rinishida uzatiladi: kNN-VC ichida `type(path) in [str, Path]`
        # deb tekshiriladi, `Path("x")` esa aslida `PosixPath` bo'lgani uchun bu
        # tekshiruv o'tmay, manzil tensor deb qabul qilinadi va xato beradi.
        matching_set = model.get_matching_set([str(reference_path)])
        print(f"  Namuna bazasi: {matching_set.shape[0]} kadr ({reference_path.name})")
        if matching_set.shape[0] < 500:  # ~10 soniyadan qisqa
            print("  [ogohlantirish] namuna juda qisqa — sifat past chiqadi.")
        _MATCHING_SETS[key] = matching_set
    return _MATCHING_SETS[key]


def mixed_text_to_converted_audio(
    text: str | None = None,
    output_path: str | Path | None = None,
    reference: str | Path = REFERENCE,
    voice: str = DEFAULT_VOICE,
    lang_code: str = DEFAULT_LANG,
    speed: float = DEFAULT_SPEED,
    topk: int = DEFAULT_TOPK,
    device: str | None = None,
) -> Path:
    """Aralash matnni audioga o'girish; inglizcha qismi namuna ovoziga o'tkaziladi.

    Args:
        text: O'qiladigan matn. Inglizcha qismlari `[start-en]...[end-en]` bilan
            belgilanadi. Berilmasa (yoki bo'sh bo'lsa), input orqali so'raladi.
        output_path: Natijaviy .wav fayl manzili. Berilmasa, input orqali so'raladi
            (default qiymat: joriy papkadagi `mixed-converted.wav`).
        reference: Ovoz namunasi (.wav) — Navoiy TTS ham, kNN-VC ham shundan
            foydalanadi (default: `navoiy-tts/demo/xurmo.wav`).
        voice: Kokoro ovozi — inglizcha bo'lakning TALAFFUZI shundan olinadi
            (ovozning o'zi keyin namunaga almashtiriladi).
        lang_code: Kokoro til kodi (default: a — amerikacha ingliz).
        speed: Kokoro nutq tezligi.
        topk: kNN dagi qo'shnilar soni (default: 4).
        device: cpu / cuda. Berilmasa, o'zi aniqlanadi.

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

    reference = Path(reference).expanduser().resolve()
    if not reference.is_file():
        fail(f"Ovoz namunasi topilmadi: {reference}")

    segments = split_segments(text)
    if not segments:
        fail("Matn bo'sh — o'qiladigan bo'lak topilmadi.")

    print(f"\n  {len(segments)} ta bo'lak:")
    for position, (lang, chunk) in enumerate(segments, start=1):
        engine = "Kokoro + kNN-VC" if lang == "en" else "Navoiy"
        print(f"    {position}. [{lang}] {engine:16} {chunk[:60]!r}")

    import numpy
    import soundfile

    device = device or resolve_device()
    started = time.monotonic()

    parts: list[numpy.ndarray] = []
    with tempfile.TemporaryDirectory() as workdir:
        for position, (lang, chunk) in enumerate(segments, start=1):
            part_path = Path(workdir) / f"{position:02d}-{lang}.wav"

            if lang == "en":
                kokoro_to_audio(chunk, part_path, voice=voice, lang_code=lang_code, speed=speed)
                data = _convert(part_path, reference, topk, device)
            else:
                _navoiy(reference).synthesize(chunk, part_path)
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
    print(f"  Sarflangan vaqt: {format_duration(time.monotonic() - started)}")
    return output_path


def _convert(part_path: Path, reference: Path, topk: int, device: str):
    """Kokoro yasagan bo'lakni namuna ovoziga o'tkazib, 24 kHz numpy massiv qaytarish."""
    import torchaudio

    model = load_model(device)
    matching_set = _matching_set(model, reference, device)

    query_seq = model.get_features(str(part_path))
    if query_seq.shape[0] < MIN_FRAMES_WARNING:
        print(
            f"      [ogohlantirish] bo'lak juda qisqa ({query_seq.shape[0]} kadr) — "
            "ovoz o'zgarishi noaniq chiqishi mumkin."
        )

    audio = model.match(query_seq, matching_set, topk=topk).cpu()

    # kNN-VC 16 kHz qaytaradi, o'zbekcha bo'laklar esa 24 kHz — birlashtirishdan
    # oldin bitta chastotaga keltiramiz, aks holda inglizcha qism sekin va past
    # ovozda eshitiladi.
    audio = torchaudio.functional.resample(audio, KNNVC_SAMPLE_RATE, SAMPLE_RATE)
    print(f"      ovoz o'zgartirildi ({audio.shape[-1] / SAMPLE_RATE:.1f}s)")
    return audio.numpy()


if __name__ == "__main__":
    try:
        mixed_text_to_converted_audio()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
