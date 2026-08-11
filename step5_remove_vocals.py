"""5-bosqich: videodagi ovozdan shaxs nutqini (vokalni) ajratib olib tashlash.

Demucs (Meta'ning ochiq modeli) orqali amalga oshiriladi. Natijada asl ovozdan
faqat FON qoladi: musiqa, effektlar, tabiat tovushlari — gapirgan odam ovozi esa
olib tashlanadi. 6-bosqich shu fon ustiga o'zbekcha audiolarni qo'yadi.

Qo'lda qilinganda bu shunga teng:
    ffmpeg -i film.mp4 -vn -ar 44100 -ac 2 audio.wav
    demucs --two-stems=vocals audio.wav
    # natija: separated/htdemucs/audio/no_vocals.wav

O'rnatish:
    pip install demucs

Environment o'zgaruvchilari:
    DEMUCS_MODEL   — model nomi (default: htdemucs)
    DEMUCS_DEVICE  — cpu / cuda / mps (default: cuda bo'lsa cuda, aks holda cpu)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from utils import ask_path, ask_yes_no, fail, run_ffmpeg

DEMUCS_MODEL = os.environ.get("DEMUCS_MODEL", "htdemucs")

# Demucs 44.1 kHz stereo audio bilan ishlashga o'rgatilgan — 1-bosqichdagi
# 16 kHz mono fayl (whisper uchun) bu yerga to'g'ri kelmaydi.
SAMPLE_RATE = 44100
CHANNELS = 2


def remove_vocals(
    video_path: str | Path | None = None,
    output_path: str | Path | None = None,
    model: str = DEMUCS_MODEL,
) -> Path:
    """Videoning ovozidan nutqni olib tashlab, fon audiosini qaytarish.

    Args:
        video_path: Manba video fayl manzili. Berilmasa, input orqali so'raladi.
        output_path: Natijaviy fon audiosi. Berilmasa, input orqali so'raladi
            (default qiymat: `<nom>-background.wav`).
        model: Demucs modeli (default: htdemucs).

    Returns:
        Fon audiosi (nutqsiz) faylining manzili.
    """
    if video_path is None:
        video_path = ask_path("Video fayl manzilini kiriting", must_exist=True)
    video_path = Path(video_path).expanduser().resolve()
    if not video_path.is_file():
        fail(f"Video fayl topilmadi: {video_path}")

    if output_path is None:
        output_path = ask_path(
            "Fon audiosi qayerga saqlansin",
            default=video_path.with_name(f"{video_path.stem}-background.wav"),
        )
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Ajratish uzoq davom etadi — tayyor natija bo'lsa, qaytadan hisoblamaymiz.
    if output_path.is_file() and output_path.stat().st_size > 0:
        if not ask_yes_no(f"  {output_path.name} allaqachon mavjud. Qaytadan ajratilsinmi?", default=False):
            print("  Mavjud fayl ishlatildi.")
            return output_path

    stereo_audio = video_path.with_name(f"{video_path.stem}-44k.wav")
    run_ffmpeg(
        [
            "-i", str(video_path),
            "-vn",
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
            str(stereo_audio),
        ],
        f"demucs uchun audio ajratilmoqda ({SAMPLE_RATE} Hz stereo)",
    )

    work_dir = output_path.parent / f".demucs-{video_path.stem}"
    try:
        separated = run_demucs(stereo_audio, work_dir, model)
        shutil.move(str(separated), str(output_path))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        stereo_audio.unlink(missing_ok=True)

    print(f"  Fon audiosi tayyor: {output_path.name}")
    return output_path


def run_demucs(audio_path: Path, work_dir: Path, model: str) -> Path:
    """`demucs --two-stems=vocals` ni ishga tushirib, nutqsiz faylni topish."""
    device = resolve_device()
    print(f"  Demucs: {model} | Qurilma: {device}")
    print("  Nutq fondan ajratilmoqda (CPU da bu uzoq davom etadi)...")

    process = subprocess.run(
        [
            sys.executable, "-m", "demucs",
            "--two-stems=vocals",
            "-n", model,
            "-d", device,
            "-o", str(work_dir),
            str(audio_path),
        ]
    )
    if process.returncode != 0:
        fail("demucs xatolik bilan tugadi. O'rnatilganini tekshiring: pip install demucs")

    matches = sorted(work_dir.glob("**/no_vocals.*"))
    if not matches:
        fail(f"demucs natijasi topilmadi: {work_dir}")
    return matches[0]


def resolve_device() -> str:
    """Qaysi qurilmada hisoblashni aniqlash."""
    forced = os.environ.get("DEMUCS_DEVICE")
    if forced:
        return forced

    try:
        import torch
    except ImportError:
        return "cpu"

    if torch.cuda.is_available():
        return "cuda"
    # Apple Silicon uchun `DEMUCS_DEVICE=mps` ni sinab ko'rish mumkin — ancha
    # tezroq ishlaydi, lekin ba'zi torch versiyalarida xatolik beradi.
    return "cpu"


if __name__ == "__main__":
    result = remove_vocals()
    print(f"Tayyor: {result}")
