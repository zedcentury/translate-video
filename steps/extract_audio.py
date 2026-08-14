"""2-bosqich: ffmpeg orqali videodan audio qismini ajratib olish.

Bu yerga ASL video beriladi (1-bosqichdagi ovozsiz nusxa emas) — transkripsiya
uchun nutq faqat asl videoda qolgan.
"""

from __future__ import annotations

import sys
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.common import ask_path, fail, run_ffmpeg  # noqa: E402


def extract_audio(video_path: str | Path | None = None, audio_path: str | Path | None = None) -> Path:
    """Videodan audio ajratib olib, uni `audio_path` ga saqlash.

    Args:
        video_path: Manba video fayl manzili. Berilmasa, input orqali so'raladi.
        audio_path: Natijaviy audio fayl manzili. Berilmasa, input orqali so'raladi
            (default qiymat: video bilan yonma-yon, `.wav` kengaytmasi bilan).

    Returns:
        Yaratilgan audio faylning manzili.
    """
    if video_path is None:
        video_path = ask_path("Video fayl manzilini kiriting (/path/to/docker/docker.mp4)", must_exist=True)
    video_path = Path(video_path).expanduser().resolve()
    if not video_path.is_file():
        fail(f"Video fayl topilmadi: {video_path}")

    if audio_path is None:
        audio_path = ask_path(
            "Audio fayl qayerga saqlansin",
            default=video_path.with_suffix(".wav"),
        )
    audio_path = Path(audio_path).expanduser().resolve()
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    # 16 kHz mono PCM — transkripsiya modellari (whisper) uchun eng qulay format.
    run_ffmpeg(
        [
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(audio_path),
        ],
        f"audio ajratilmoqda -> {audio_path.name}",
    )
    return audio_path


if __name__ == "__main__":
    result = extract_audio()
    print(f"Tayyor: {result}")
