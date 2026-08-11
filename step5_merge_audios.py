"""5-bosqich: audiolarni videoga timestamp bo'yicha biriktirib, yangi video yasash.

Audio fayl nomining o'zi uning qaysi vaqtda boshlanishini bildiradi:
    00-01-02-500.wav  ->  00:01:02,500 dan boshlab qo'yiladi.

Videoning ASL OVOZI saqlanadi — yangi audiolar uning ustiga qo'shiladi.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from utils import ask_path, fail, run_ffmpeg

AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac")

# Asl ovozning umumiy balandligi (1.0 — o'zgarishsiz).
ORIGINAL_VOLUME = 1.0

# Yangi audio eshitilayotgan paytda asl ovoz shu darajaga pasaytiriladi
# (0.05 — 5%). Qolgan joylarda asl ovoz ORIGINAL_VOLUME darajasida qoladi.
DUCK_VOLUME = 0.15

# Pasaytirish yangi audiodan biroz oldin boshlanib, biroz keyin tugaydi —
# ovoz balandligi keskin sakramasligi uchun.
DUCK_MARGIN_MS = 150

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


def probe_duration(audio_path: Path) -> float:
    """Audio faylning davomiyligini (soniyada) aniqlash."""
    process = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(process.stdout.strip())
    except ValueError:
        print(f"  [ogohlantirish] davomiyligi aniqlanmadi: {audio_path.name}")
        return 0.0


def duck_intervals(tracks: list[tuple[int, Path]]) -> list[tuple[float, float]]:
    """Asl ovoz pasaytiriladigan oraliqlar (soniyada), ustma-ust tushganlari birlashtirilgan."""
    margin = DUCK_MARGIN_MS / 1000
    raw: list[tuple[float, float]] = []
    for start_ms, audio_path in tracks:
        duration = probe_duration(audio_path)
        if duration <= 0:
            continue
        start = max(0.0, start_ms / 1000 - margin)
        raw.append((start, start_ms / 1000 + duration + margin))

    merged: list[tuple[float, float]] = []
    for start, end in sorted(raw):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def duck_expression(tracks: list[tuple[int, Path]]) -> str:
    """ffmpeg `enable` ifodasi: qaysi oraliqlarda pasaytirish yoqilishi kerak."""
    intervals = duck_intervals(tracks)
    if not intervals:
        return "0"  # hech qachon yoqilmaydi
    print(f"  Asl ovoz {len(intervals)} ta oraliqda {int(DUCK_VOLUME * 100)}% ga pasaytiriladi.")
    return "+".join(f"between(t,{start:.3f},{end:.3f})" for start, end in intervals)


def mux(video_path: Path, tracks: list[tuple[int, Path]], output_path: Path) -> None:
    """ffmpeg: har bir audioni `adelay` bilan kechiktirib, `amix` orqali birlashtirish.

    Videoning asl ovozi ham aralashmaga kiritiladi (agar mavjud bo'lsa).
    """
    inputs: list[str] = ["-i", str(video_path)]
    filters: list[str] = []
    labels: list[str] = []

    keep_original = has_audio_stream(video_path)
    if keep_original:
        # Asl ovozni kechiktirish shart emas — u videoning boshidan boshlanadi.
        # `enable` orqali faqat yangi audio eshitilayotgan oraliqlarda pasaytiriladi.
        filters.append(f"[0:a]volume={ORIGINAL_VOLUME}[orig0]")
        filters.append(
            f"[orig0]volume={DUCK_VOLUME}:enable='{duck_expression(tracks)}'[orig]"
        )
        labels.append("[orig]")
    else:
        print("  [ogohlantirish] videoda audio oqimi yo'q — faqat yangi audiolar qo'shiladi.")

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
                "-map", "0:v",
                "-map", "[aout]",     # asl ovoz + yangi audiolar aralashmasi
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
