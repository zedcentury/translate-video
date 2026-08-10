"""2-bosqich: audio fayldan .srt (transkripsiya) generatsiya qilish.

openai-whisper `large-v3` modeli orqali amalga oshiriladi.

O'rnatish:
    pip install openai-whisper

Model birinchi marta ishlatilganda ~3 GB hajmda yuklab olinadi va
`~/.cache/whisper` papkasida saqlanadi (WHISPER_DOWNLOAD_ROOT orqali o'zgartirsa bo'ladi).

Environment o'zgaruvchilari:
    WHISPER_MODEL          — model nomi (default: large-v3; tezroq variant: large-v3-turbo)
    WHISPER_DEVICE         — cpu / cuda / mps (default: cuda bo'lsa cuda, aks holda cpu)
    WHISPER_DOWNLOAD_ROOT  — model fayllari saqlanadigan papka
"""

from __future__ import annotations

import os
from pathlib import Path

from srt_utils import Cue, write_srt
from utils import ask_path, ask_yes_no, fail

DEFAULT_LANGUAGE = "en"
DEFAULT_MODEL = os.environ.get("WHISPER_MODEL", "large-v3")

# Ketma-ket segmentlarni bir-biriga bog'lash kontekstni yaxshilaydi, lekin
# jimjitlik joylarida modelni "tsikl"ga tushirib, bir xil gapni takrorlab
# yozishi mumkin. Dublyaj uchun barqarorlik muhimroq — shuning uchun False.
CONDITION_ON_PREVIOUS_TEXT = False

# True qilinsa, har bir so'zning vaqti aniqlanadi (segment chegaralari aniqroq
# bo'ladi), lekin transkripsiya sezilarli sekinlashadi.
WORD_TIMESTAMPS = False


def generate_srt(
    audio_path: str | Path | None = None,
    srt_path: str | Path | None = None,
    language: str = DEFAULT_LANGUAGE,
    model_name: str = DEFAULT_MODEL,
) -> Path:
    """Audio fayldagi nutqni matnga o'girib, .srt fayl yaratish.

    Args:
        audio_path: Manba audio fayl manzili. Berilmasa, input orqali so'raladi.
        srt_path: Natijaviy .srt fayl manzili. Berilmasa, input orqali so'raladi
            (default qiymat: audio bilan yonma-yon, `.srt` kengaytmasi bilan).
        language: Audiodagi nutq tili (default: "en"). None berilsa, whisper
            tilni o'zi aniqlaydi.
        model_name: whisper modeli (default: "large-v3").

    Returns:
        Yaratilgan .srt faylning manzili.
    """
    if audio_path is None:
        audio_path = ask_path("Audio fayl manzilini kiriting", must_exist=True)
    audio_path = Path(audio_path).expanduser().resolve()
    if not audio_path.is_file():
        fail(f"Audio fayl topilmadi: {audio_path}")

    if srt_path is None:
        srt_path = ask_path(
            "Transkripsiya .srt fayli qayerga saqlansin",
            default=audio_path.with_suffix(".srt"),
        )
    srt_path = Path(srt_path).expanduser().resolve()

    # Transkripsiya uzoq davom etadi — tayyor natija bo'lsa, qaytadan hisoblamaymiz.
    if srt_path.is_file() and srt_path.stat().st_size > 0:
        if not ask_yes_no(f"  {srt_path.name} allaqachon mavjud. Qaytadan generatsiya qilinsinmi?", default=False):
            print("  Mavjud fayl ishlatildi.")
            return srt_path

    segments = transcribe(audio_path, language=language, model_name=model_name)
    cues = segments_to_cues(segments)
    if not cues:
        fail(f"{audio_path.name} ichidan nutq topilmadi (bo'sh natija).")

    write_srt(cues, srt_path)
    print(f"  {len(cues)} ta segment yozildi.")
    return srt_path


def transcribe(audio_path: Path, language: str | None, model_name: str) -> list[dict]:
    """whisper orqali audioni transkripsiya qilib, segmentlar ro'yxatini qaytarish."""
    try:
        import whisper
    except ImportError:
        fail("openai-whisper topilmadi. O'rnating: pip install openai-whisper")

    device = resolve_device()
    print(f"  Model: {model_name} | Qurilma: {device} | Til: {language or 'avto'}")
    print("  Model yuklanmoqda (birinchi marta bir necha GB yuklab olinadi)...")

    model = whisper.load_model(
        model_name,
        device=device,
        download_root=os.environ.get("WHISPER_DOWNLOAD_ROOT") or None,
    )

    print("  Transkripsiya boshlandi, bu biroz vaqt oladi...")
    result = model.transcribe(
        str(audio_path),
        language=language,
        task="transcribe",
        verbose=False,  # True qilinsa, har bir segment ekranga chiqadi
        fp16=(device == "cuda"),  # CPU/MPS da fp16 ishlamaydi
        condition_on_previous_text=CONDITION_ON_PREVIOUS_TEXT,
        word_timestamps=WORD_TIMESTAMPS,
    )
    return result.get("segments", [])


def resolve_device() -> str:
    """Qaysi qurilmada hisoblashni aniqlash."""
    forced = os.environ.get("WHISPER_DEVICE")
    if forced:
        return forced

    try:
        import torch
    except ImportError:
        return "cpu"

    if torch.cuda.is_available():
        return "cuda"
    # Apple Silicon (mps) whisper'da to'liq qo'llab-quvvatlanmaydi — ba'zi
    # operatsiyalar xatolik beradi, shuning uchun default cpu.
    return "cpu"


def segments_to_cues(segments: list[dict]) -> list[Cue]:
    """whisper segmentlarini Cue ro'yxatiga aylantirish."""
    cues: list[Cue] = []
    for segment in segments:
        text = " ".join(str(segment.get("text", "")).split())
        if not text:
            continue
        cues.append(
            Cue(
                index=len(cues) + 1,
                start_ms=int(round(float(segment["start"]) * 1000)),
                end_ms=int(round(float(segment["end"]) * 1000)),
                text=text,
            )
        )
    return cues


if __name__ == "__main__":
    result = generate_srt()
    print(f"Tayyor: {result}")
