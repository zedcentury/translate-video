"""5-bosqich: audiolarni videoga timestamp bo'yicha biriktirib, yangi video yasash.

Audio fayl nomining o'zi uning qaysi vaqtda boshlanishini bildiradi:
    00-01-02-500.wav  ->  00:01:02,500 dan boshlab qo'yiladi.

Videoning asl ovozi natijaviy faylga ko'chirilmaydi (faqat video oqimi olinadi),
shuning uchun alohida "ovozni o'chirish" bosqichi kerak emas.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from utils import ask_path, fail, run_ffmpeg

AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac")

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
        video_path: Manba video fayl manzili. Berilmasa, input orqali so'raladi.
        audios_dir: Audiolar joylashgan papka manzili. Berilmasa, input orqali
            so'raladi (default qiymat: video yonidagi `audios` papkasi).
        output_path: Natijaviy video manzili. Berilmasa, `<nom>-uz.<kengaytma>`.

    Returns:
        Yaratilgan video faylning manzili.
    """
    if video_path is None:
        video_path = ask_path("Video fayl manzilini kiriting", must_exist=True)
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
        output_path = video_path.with_name(f"{video_path.stem}-uz{video_path.suffix}")
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


def mux(video_path: Path, tracks: list[tuple[int, Path]], output_path: Path) -> None:
    """ffmpeg: har bir audioni `adelay` bilan kechiktirib, `amix` orqali birlashtirish."""
    inputs: list[str] = ["-i", str(video_path)]
    filters: list[str] = []
    labels: list[str] = []

    for position, (start_ms, audio_path) in enumerate(tracks, start=1):
        inputs += ["-i", str(audio_path)]
        label = f"a{position}"
        filters.append(f"[{position}:a]adelay=delays={start_ms}:all=1[{label}]")
        labels.append(f"[{label}]")

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
                "-map", "0:v",        # faqat video oqimi — asl ovoz olinmaydi
                "-map", "[aout]",
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
