"""2-bosqich: audio fayldan .srt (transkripsiya) generatsiya qilish.

TODO: openai-whisper orqali amalga oshiriladi.

Reja:
    pip install openai-whisper

    import whisper
    model = whisper.load_model("medium")        # tiny/base/small/medium/large
    result = model.transcribe(str(audio_path), language=language, task="transcribe")

    So'ngra `result["segments"]` ichidagi har bir segment uchun
    (segment["start"], segment["end"], segment["text"]) qiymatlaridan
    srt_utils.Cue yasab, srt_utils.write_srt(cues, srt_path) chaqiriladi.
    Segment vaqtlari soniyada (float) keladi -> int(start * 1000) qilib ms ga o'tkaziladi.

    Muqobil variant: whisper CLI
        whisper <audio> --model medium --language en --output_format srt --output_dir <dir>

Hozircha bu bosqich QO'LDA bajariladi: foydalanuvchi srt faylni o'zi tayyorlab,
tasdiqlaydi va dastur faylning mavjudligini tekshiradi.
"""

from __future__ import annotations

from pathlib import Path

from utils import ask_path, confirm, fail

DEFAULT_LANGUAGE = "en"


def generate_srt(
    audio_path: str | Path | None = None,
    srt_path: str | Path | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> Path:
    """Audio fayldagi nutqni matnga o'girib, .srt fayl yaratish.

    Args:
        audio_path: Manba audio fayl manzili. Berilmasa, input orqali so'raladi.
        srt_path: Natijaviy .srt fayl manzili. Berilmasa, input orqali so'raladi
            (default qiymat: audio bilan yonma-yon, `.srt` kengaytmasi bilan).
        language: Audiodagi nutq tili (default: "en").

    Returns:
        Yaratilgan .srt faylning manzili.
    """
    if audio_path is None:
        audio_path = ask_path("Audio fayl manzilini kiriting", must_exist=True)
    audio_path = Path(audio_path).expanduser().resolve()

    if srt_path is None:
        srt_path = ask_path(
            "Transkripsiya .srt fayli qayerga saqlansin",
            default=audio_path.with_suffix(".srt"),
        )
    srt_path = Path(srt_path).expanduser().resolve()

    # --- TODO: shu yerga openai-whisper orqali transkripsiya kodi yoziladi ---

    print(f"  Til: {language}")
    print(f"  Kutilayotgan fayl: {srt_path}")
    confirm(f"  Transkripsiya hozircha qo'lda bajariladi. {srt_path.name} tayyormi?")
    if not srt_path.is_file():
        fail(f"{srt_path} topilmadi.")
    return srt_path


if __name__ == "__main__":
    result = generate_srt()
    print(f"Tayyor: {result}")
