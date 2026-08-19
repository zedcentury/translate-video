"""Videodagi odam nutqini (vokalni) olib tashlab, yangi video hosil qilish.

`steps/remove_audio.py` ga muqobil bosqich. U audio oqimini butunlay tashlab
yuboradi, bu yerda esa ovoz saqlanadi — faqat gapirgan odam ovozi olib
tashlanadi. Natijada musiqa, effektlar va boshqa fon tovushlari joyida qoladi.

Ish tartibi:
    1. videodan 44.1 kHz stereo audio ajratiladi (demucs shu formatni kutadi);
    2. demucs `--two-stems=vocals` bilan nutqni fondan ajratadi;
    3. nutqsiz fon audiosi videoga yagona audio oqim sifatida biriktiriladi.

Natija: `<nom>-removed-vocal.<kengaytma>` — tasvir qayta kodlanmaydi
(`-c:v copy`), shuning uchun sifat yo'qolmaydi.

Qo'lda qilinganda bu shunga teng:
    ffmpeg -i film.mp4 -vn -ar 44100 -ac 2 audio.wav
    demucs --two-stems=vocals audio.wav
    # natija: separated/htdemucs/audio/no_vocals.wav
    ffmpeg -i film.mp4 -i no_vocals.wav -map 0:v -map 1:a -c:v copy -c:a aac film-removed-vocal.mp4

O'rnatish:
    pip install demucs

Environment o'zgaruvchilari:
    DEMUCS_MODEL   — model nomi (default: htdemucs)
    DEMUCS_DEVICE  — cpu / cuda / mps (default: cuda bo'lsa cuda, aks holda cpu)

Ishga tushirish (loyiha ildizidan):
    python steps/remove_vocals.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.common import ask_path, ask_yes_no, fail, run_ffmpeg  # noqa: E402

DEMUCS_MODEL = os.environ.get("DEMUCS_MODEL", "htdemucs")

# Natijaviy video nomiga qo'shiladigan qo'shimcha: docker9 -> docker9-removed-vocal
OUTPUT_SUFFIX = "-removed-vocal"

# Demucs 44.1 kHz stereo audio bilan ishlashga o'rgatilgan — transkripsiya uchun
# ishlatiladigan 16 kHz mono fayl (steps/extract_audio.py) bu yerga to'g'ri kelmaydi.
SAMPLE_RATE = 44100
CHANNELS = 2

AUDIO_CODEC = "aac"
AUDIO_BITRATE = "192k"


def remove_vocals(
    video_path: str | Path | None = None,
    output_path: str | Path | None = None,
    background_audio: str | Path | None = None,
    model: str = DEMUCS_MODEL,
    redo: bool | None = None,
) -> Path:
    """Videodan nutqni olib tashlab, faqat fon ovozi qolgan video yaratish.

    Args:
        video_path: Manba video fayl manzili. Berilmasa, input orqali so'raladi.
        output_path: Natijaviy video manzili. Berilmasa, input orqali so'raladi
            (default qiymat: `<nom>-removed-vocal.<kengaytma>`).
        background_audio: Nutqsiz fon audiosi qayerga saqlansin. Berilmasa,
            u vaqtinchalik fayl sifatida yaratilib, oxirida o'chiriladi.
        model: Demucs modeli (default: htdemucs).
        redo: Natija allaqachon mavjud bo'lsa nima qilish kerak. `None` — so'raladi,
            `True` — qaytadan hisoblanadi, `False` — mavjud fayl ishlatiladi.
            Boshqa koddan chaqirilganda aniq qiymat bering, aks holda quvur
            o'rtasida savol berilib qoladi.

    Returns:
        Yaratilgan videoning manzili.
    """
    if video_path is None:
        video_path = ask_path("Video fayl manzilini kiriting (/path/to/docker/docker.mp4)", must_exist=True)
    video_path = Path(video_path).expanduser().resolve()
    if not video_path.is_file():
        fail(f"Video fayl topilmadi: {video_path}")

    if output_path is None:
        output_path = ask_path(
            "Nutqsiz video qayerga saqlansin",
            default=video_path.with_name(f"{video_path.stem}{OUTPUT_SUFFIX}{video_path.suffix}"),
        )
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path == video_path:
        fail("Natija manba video bilan bir xil bo'lishi mumkin emas.")

    # Nutqni ajratish uzoq davom etadi — tayyor natija bo'lsa, qaytadan hisoblamaymiz.
    if is_ready(output_path):
        if redo is None:
            redo = ask_yes_no(
                f"  {output_path.name} allaqachon mavjud. Qaytadan yasalsinmi?", default=False
            )
        if not redo:
            print("  Mavjud fayl ishlatildi.")
            return output_path

    # Fon audiosi alohida so'ralmagan bo'lsa, u faqat oraliq natija — oxirida o'chiriladi.
    keep_audio = background_audio is not None
    if background_audio is None:
        background_audio = output_path.with_name(f"{video_path.stem}-no-vocals.wav")
    background_audio = Path(background_audio).expanduser().resolve()
    background_audio.parent.mkdir(parents=True, exist_ok=True)

    try:
        extract_background(video_path, background_audio, model)
        mux(video_path, background_audio, output_path)
    finally:
        if not keep_audio:
            background_audio.unlink(missing_ok=True)

    if keep_audio:
        print(f"  Fon audiosi saqlandi: {background_audio}")
    return output_path


def extract_background(video_path: Path, background_audio: Path, model: str) -> Path:
    """Videoning ovozidan nutqni ajratib tashlab, fon audiosini yozish."""
    stereo_audio = background_audio.with_name(f"{video_path.stem}-44k.wav")
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

    work_dir = background_audio.parent / f".demucs-{video_path.stem}"
    try:
        separated = run_demucs(stereo_audio, work_dir, model)
        background_audio.unlink(missing_ok=True)
        shutil.move(str(separated), str(background_audio))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        stereo_audio.unlink(missing_ok=True)

    print(f"  Fon audiosi tayyor: {background_audio.name}")
    return background_audio


def mux(video_path: Path, background_audio: Path, output_path: Path) -> Path:
    """Nutqsiz fon audiosini videoga yagona audio oqim sifatida biriktirish."""
    run_ffmpeg(
        [
            "-i", str(video_path),
            "-i", str(background_audio),
            "-map", "0:v",      # videoning tasvir oqimi
            "-map", "1:a",      # asl ovoz o'rniga nutqsiz fon audiosi
            "-c:v", "copy",
            "-c:a", AUDIO_CODEC,
            "-b:a", AUDIO_BITRATE,
            str(output_path),
        ],
        f"nutqsiz ovoz videoga biriktirilmoqda -> {output_path.name}",
    )
    return output_path


def run_demucs(audio_path: Path, work_dir: Path, model: str, stem: str = "no_vocals") -> Path:
    """`demucs --two-stems=vocals` ni ishga tushirib, kerakli oqimni topish.

    Demucs bir yo'la ikkita fayl yasaydi: `vocals` (nutq) va `no_vocals` (fon).
    `stem` argumenti shulardan qaysi biri qaytarilishini belgilaydi —
    `utils/clean_audio.py` teskarisini, ya'ni `vocals` ni oladi.
    """
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

    matches = sorted(work_dir.glob(f"**/{stem}.*"))
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


def is_ready(path: Path) -> bool:
    """Fayl mavjud va bo'sh emasmi."""
    return path.is_file() and path.stat().st_size > 0


if __name__ == "__main__":
    result = remove_vocals()
    print(f"Tayyor: {result}")
