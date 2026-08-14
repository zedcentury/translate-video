"""7-bosqich: audiolarni videoga timestamp bo'yicha biriktirib, yangi video yasash.

Audio fayl nomining o'zi uning qaysi vaqtda boshlanishini bildiradi:
    00-01-02-500.wav  ->  00:01:02,500 dan boshlab qo'yiladi.

Bu bosqichga 1-bosqichdan chiqqan video beriladi:
    `<nom>-no-audio.mp4`       — ovozsiz (course rejimi), natijada faqat o'zbekcha nutq;
    `<nom>-removed-vocal.mp4`  — fon ovozi qolgan (movie rejimi), u ham aralashmaga tushadi.

Natija: `<nom>-result.mp4` — nom asl video nomidan olinadi, ya'ni yuqoridagi
qo'shimchalar tashlab yuboriladi (`docker9-no-audio.mp4` -> `docker9-result.mp4`).

Audio oqimi bor video berilganda uning ovozi aralashmaga qo'shiladi — balandligi
`ORIGINAL_VOLUME` bilan boshqariladi.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.common import ask_path, fail, run_ffmpeg  # noqa: E402

AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac")

# Yakuniy video nomiga qo'shiladigan qo'shimcha: docker9 -> docker9-result
OUTPUT_SUFFIX = "-result"

# Manba video 1-bosqich natijasi bo'lgani uchun nomida shu qo'shimchalar turadi.
# Yakuniy nom asl video nomidan hosil bo'lishi uchun ularni olib tashlaymiz:
#   docker9-no-audio.mp4 -> docker9-result.mp4
STEP1_SUFFIXES = ("-no-audio", "-removed-vocal")

# Videoning o'z ovozining balandligi (1.0 — o'zgarishsiz). Odatdagi quvurda
# video 1-bosqichda ovozsiz qilingani uchun bu qiymat ishlatilmaydi; u faqat
# audio oqimi bor video berilganda hisobga olinadi.
ORIGINAL_VOLUME = 1.0

# 00-01-02-500 (soat-daqiqa-soniya-millisekund). Ajratuvchi belgi ixtiyoriy,
# millisekund qismi bo'lmasa 0 deb qabul qilinadi.
FILENAME_RE = re.compile(
    r"^(\d{1,2})[-_.:,](\d{1,2})[-_.:,](\d{1,2})(?:[-_.:,](\d{1,3}))?$"
)


def merge_audios(
    video_path: str | Path | None = None,
    audios_dir: str | Path | None = None,
    output_path: str | Path | None = None,
) -> Path:
    """Audiolarni videoga fayl nomidagi vaqt bo'yicha biriktirish.

    Args:
        video_path: Manba video fayl manzili (1-bosqich natijasi). Berilmasa,
            input orqali so'raladi.
        audios_dir: Audiolar joylashgan papka manzili. Berilmasa, input orqali
            so'raladi (default qiymat: video yonidagi `audios` papkasi).
        output_path: Natijaviy video manzili. Berilmasa, `<nom>-result.<kengaytma>`
            (`<nom>` — 1-bosqich qo'shimchasisiz, ya'ni asl video nomi).

    Returns:
        Yaratilgan video faylning manzili.
    """
    if video_path is None:
        video_path = ask_path(
            "Ovozsiz video fayl manzilini kiriting "
            "(/path/to/docker/docker-no-audio.mp4)",
            must_exist=True,
        )
    video_path = Path(video_path).expanduser().resolve()
    if not video_path.is_file():
        fail(f"Video fayl topilmadi: {video_path}")

    if audios_dir is None:
        audios_dir = ask_path(
            "Audiolar joylashgan papka manzilini kiriting",
            default=video_path.parent / "audios",
            must_exist=True,
            must_be_dir=True,
        )
    audios_dir = Path(audios_dir).expanduser().resolve()
    if not audios_dir.is_dir():
        fail(f"Papka topilmadi: {audios_dir}")

    if output_path is None:
        output_path = video_path.with_name(f"{base_stem(video_path)}{OUTPUT_SUFFIX}{video_path.suffix}")
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tracks = collect_tracks(audios_dir)
    if not tracks:
        fail(
            f"{audios_dir} ichida vaqt ko'rinishidagi nomga ega audio topilmadi.\n"
            f"Kutilgan format: 00-01-02-500.wav"
        )
    print(f"  {len(tracks)} ta audio fayl topildi.")

    mux(video_path, tracks, output_path)
    return output_path


def base_stem(video_path: Path) -> str:
    """1-bosqich qo'shgan qo'shimchani olib tashlab, asl video nomini qaytarish."""
    stem = video_path.stem
    for suffix in STEP1_SUFFIXES:
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def collect_tracks(audios_dir: Path) -> list[tuple[int, Path]]:
    """Papkadagi audiolarni (boshlanish_ms, manzil) ko'rinishida, vaqt bo'yicha saralab qaytarish."""
    tracks: list[tuple[int, Path]] = []
    for path in sorted(audios_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        start_ms = parse_start_ms(path.stem)
        if start_ms is None:
            print(f"  [ogohlantirish] nomi vaqtga o'xshamagani uchun tashlab ketildi: {path.name}")
            continue
        tracks.append((start_ms, path))
    return sorted(tracks, key=lambda item: item[0])


def parse_start_ms(stem: str) -> int | None:
    """Fayl nomidan boshlanish vaqtini millisekundda aniqlash."""
    match = FILENAME_RE.match(stem)
    if match is None:
        return None
    hours, minutes, seconds, millis = match.groups()
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1000
        + int((millis or "0").ljust(3, "0"))
    )


def has_audio_stream(video_path: Path) -> bool:
    """Videoda audio oqimi bor-yo'qligini aniqlash."""
    process = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    return bool(process.stdout.strip())


def mux(video_path: Path, tracks: list[tuple[int, Path]], output_path: Path) -> None:
    """ffmpeg: har bir audioni `adelay` bilan kechiktirib, `amix` orqali birlashtirish.

    Videoda audio oqimi bo'lsa (ya'ni ovozsiz nusxa emas), u ham aralashmaga
    kiritiladi.
    """
    inputs: list[str] = ["-i", str(video_path)]
    filters: list[str] = []
    labels: list[str] = []
    next_input = 1  # 0 — video

    original_stream = "0:a" if has_audio_stream(video_path) else None
    if original_stream is None:
        print("  Video ovozsiz — faqat o'zbekcha audiolar qo'shiladi.")
    else:
        # Asl ovozni kechiktirish shart emas — u videoning boshidan boshlanadi.
        print(f"  Videoning o'z ovozi ham aralashmaga qo'shiladi (volume={ORIGINAL_VOLUME}).")
        filters.append(f"[{original_stream}]volume={ORIGINAL_VOLUME}[orig]")
        labels.append("[orig]")

    for start_ms, audio_path in tracks:
        inputs += ["-i", str(audio_path)]
        label = f"a{next_input}"
        filters.append(f"[{next_input}:a]adelay=delays={start_ms}:all=1[{label}]")
        labels.append(f"[{label}]")
        next_input += 1

    filters.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0[aout]"
    )

    # Audiolar ko'p bo'lganda filtr matni juda uzayadi, shuning uchun fayldan o'qitamiz.
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        handle.write(";\n".join(filters))
        script_path = Path(handle.name)

    try:
        run_ffmpeg(
            [
                *inputs,
                "-filter_complex_script", str(script_path),
                "-map", "0:v",
                "-map", "[aout]",     # yangi audiolar (+ bo'lsa, videoning o'z ovozi)
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                str(output_path),
            ],
            f"yakuniy video yig'ilmoqda -> {output_path.name}",
        )
    finally:
        script_path.unlink(missing_ok=True)


if __name__ == "__main__":
    result = merge_audios()
    print(f"Tayyor: {result}")
