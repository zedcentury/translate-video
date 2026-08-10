#!/usr/bin/env python3
"""Ingliz tilidagi videoni o'zbek tilida gapiriladigan variantga o'tkazish.

Bosqichlar:
    1. Video fayl manzili so'raladi.
    2. ffmpeg orqali videodan audio ajratib olinadi.
    3. (QO'LDA) <video>.srt fayli tayyorlanadi -> tasdiqlash so'raladi.
    4. (QO'LDA) <video>-uz.srt fayli tayyorlanadi -> tasdiqlash so'raladi.
    5. Har bir o'zbekcha subtitr aisha-ai orqali audioga o'giriladi (audios/).
    6. ffmpeg orqali asosiy videoning ovozsiz nusxasi olinadi.
    7. Generatsiya qilingan audiolar srt dagi start vaqti bo'yicha videoga biriktiriladi.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

try:
    from aisha_ai import AishaApiError, AishaClient, AishaConnectionError
except ImportError:  # pragma: no cover
    print("Xatolik: aisha-ai kutubxonasi topilmadi. O'rnating: pip install aisha-ai")
    raise SystemExit(1)


# --- Sozlamalar (environment orqali o'zgartirsa bo'ladi) ---------------------

TTS_LANGUAGE = os.environ.get("AISHA_TTS_LANGUAGE", "uz")
TTS_MODEL = os.environ.get("AISHA_TTS_MODEL", "Gulnoza")
TTS_MOOD = os.environ.get("AISHA_TTS_MOOD", "Neutral")
TTS_SPEED = float(os.environ.get("AISHA_TTS_SPEED", "1.0"))

MAX_TRANSCRIPT_LENGTH = 1000  # aisha-ai TTS uchun matn chegarasi
TTS_RETRY_COUNT = 3
TTS_RETRY_DELAY = 3  # soniya

TIMESTAMP_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


# --- Yordamchi tuzilmalar ----------------------------------------------------


@dataclass
class Cue:
    """SRT faylning bitta bloki."""

    index: int
    start_ms: int
    end_ms: int
    text: str

    @property
    def slug(self) -> str:
        """Boshlanish vaqtidan fayl nomi: 00:01:02,500 -> 00-01-02-500"""
        total, ms = divmod(self.start_ms, 1000)
        hours, rem = divmod(total, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours:02d}-{minutes:02d}-{seconds:02d}-{ms:03d}"


# --- Umumiy yordamchi funksiyalar -------------------------------------------


def fail(message: str) -> NoReturn:
    print(f"\n[XATOLIK] {message}")
    raise SystemExit(1)


def run_ffmpeg(args: list[str], description: str) -> None:
    """ffmpeg ni ishga tushirish va xatolikni ushlab qolish."""
    print(f"  -> {description}")
    process = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        fail(f"ffmpeg xatoligi ({description}):\n{process.stderr.strip()}")


def confirm(question: str) -> None:
    """Foydalanuvchi 'ha' deb tasdiqlaguncha so'rayveradi."""
    while True:
        answer = input(f"{question} [ha/yo'q]: ").strip().lower()
        if answer in {"ha", "h", "y", "yes", "ok", ""}:
            return
        if answer in {"yoq", "yo'q", "n", "no", "q", "exit"}:
            fail("Foydalanuvchi tomonidan bekor qilindi.")
        print("  Iltimos 'ha' yoki 'yo'q' deb javob bering.")


def ask_video_path() -> Path:
    while True:
        raw = input("Video fayl manzilini kiriting: ").strip().strip("'\"")
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        if not path.is_file():
            print(f"  Bunday fayl topilmadi: {path}")
            continue
        return path


def get_api_key() -> str:
    key = os.environ.get("AISHA_API_KEY", "").strip()
    if key:
        return key
    key = input("aisha-ai API kalitini kiriting (space.aisha.group): ").strip()
    if not key:
        fail("API kalit kiritilmadi.")
    return key


# --- SRT bilan ishlash -------------------------------------------------------


def parse_srt(path: Path) -> list[Cue]:
    """SRT faylni Cue ro'yxatiga aylantirish."""
    content = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[Cue] = []

    for block in re.split(r"\n\s*\n", content.strip()):
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        time_line_idx = next(
            (i for i, line in enumerate(lines) if TIMESTAMP_RE.search(line)), None
        )
        if time_line_idx is None:
            print(f"  [ogohlantirish] vaqt qatori topilmagan blok tashlab ketildi: {lines[0][:40]!r}")
            continue

        match = TIMESTAMP_RE.search(lines[time_line_idx])
        assert match is not None
        start_ms = to_ms(*match.group(1, 2, 3, 4))
        end_ms = to_ms(*match.group(5, 6, 7, 8))

        text = " ".join(line.strip() for line in lines[time_line_idx + 1 :]).strip()
        text = re.sub(r"<[^>]+>", "", text)  # <i>, <b> kabi teglarni olib tashlash
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue

        cues.append(Cue(index=len(cues) + 1, start_ms=start_ms, end_ms=end_ms, text=text))

    return cues


def to_ms(hours: str, minutes: str, seconds: str, millis: str) -> int:
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1000
        + int(millis.ljust(3, "0"))
    )


def split_transcript(text: str, limit: int = MAX_TRANSCRIPT_LENGTH) -> list[str]:
    """Uzun matnni TTS chegarasiga sig'adigan bo'laklarga bo'lish."""
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.!?…])\s+", text):
        while len(sentence) > limit:  # juda uzun bitta gap bo'lsa, majburan kesamiz
            if current:
                parts.append(current.strip())
                current = ""
            parts.append(sentence[:limit])
            sentence = sentence[limit:]
        if len(current) + len(sentence) + 1 > limit:
            parts.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current.strip():
        parts.append(current.strip())
    return [part for part in parts if part]


# --- Bosqichlar --------------------------------------------------------------


def extract_audio(video: Path) -> Path:
    """2-bosqich: videodan audio ajratib olish."""
    audio_path = video.with_suffix(".wav")
    run_ffmpeg(
        ["-i", str(video), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(audio_path)],
        f"audio ajratilmoqda -> {audio_path.name}",
    )
    return audio_path


def generate_tts_files(cues: list[Cue], audios_dir: Path, client: AishaClient) -> list[tuple[Cue, Path]]:
    """5-bosqich: har bir subtitr uchun alohida audio fayl generatsiya qilish."""
    audios_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[Cue, Path]] = []

    for cue in cues:
        target = audios_dir / f"{cue.slug}.wav"
        print(f"  [{cue.index}/{len(cues)}] {cue.slug} : {cue.text[:60]}")

        if target.exists() and target.stat().st_size > 0:
            print("      (mavjud fayl ishlatildi)")
            results.append((cue, target))
            continue

        chunks = split_transcript(cue.text)
        chunk_paths: list[Path] = []
        for chunk_no, chunk in enumerate(chunks, start=1):
            part_path = (
                target
                if len(chunks) == 1
                else audios_dir / f"{cue.slug}__part{chunk_no}.wav"
            )
            tts_to_file(client, chunk, part_path)
            chunk_paths.append(part_path)

        if len(chunk_paths) > 1:
            concat_audio(chunk_paths, target)
            for part in chunk_paths:
                part.unlink(missing_ok=True)

        if not target.exists() or target.stat().st_size == 0:
            fail(f"Audio fayl yaratilmadi: {target}")
        results.append((cue, target))

    return results


def tts_to_file(client: AishaClient, text: str, output: Path) -> None:
    """aisha-ai orqali matnni audioga o'girish (qayta urinishlar bilan)."""
    options: dict[str, object] = {"language": TTS_LANGUAGE}
    if TTS_LANGUAGE == "uz":
        options.update(model=TTS_MODEL, mood=TTS_MOOD, speed=TTS_SPEED)

    last_error: Exception | None = None
    for attempt in range(1, TTS_RETRY_COUNT + 1):
        try:
            client.tts(transcript=text, output_path=str(output), **options)
            return
        except (AishaApiError, AishaConnectionError) as error:
            last_error = error
            print(f"      urinish {attempt}/{TTS_RETRY_COUNT} muvaffaqiyatsiz: {error}")
            if attempt < TTS_RETRY_COUNT:
                time.sleep(TTS_RETRY_DELAY)

    fail(f"aisha-ai TTS xatoligi: {last_error}")


def concat_audio(parts: list[Path], output: Path) -> None:
    """Bir nechta audio bo'lakni bitta faylga ulash."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        for part in parts:
            handle.write(f"file '{part.as_posix()}'\n")
        list_path = Path(handle.name)
    try:
        run_ffmpeg(
            ["-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(output)],
            f"audio bo'laklari ulanmoqda -> {output.name}",
        )
    finally:
        list_path.unlink(missing_ok=True)


def strip_audio(video: Path) -> Path:
    """6-bosqich: videoning ovozsiz nusxasini olish."""
    silent_path = video.with_name(f"{video.stem}-noaudio{video.suffix}")
    run_ffmpeg(
        ["-i", str(video), "-c", "copy", "-an", str(silent_path)],
        f"ovozsiz nusxa tayyorlanmoqda -> {silent_path.name}",
    )
    return silent_path


def mux_audio(silent_video: Path, tracks: list[tuple[Cue, Path]], output: Path) -> None:
    """7-bosqich: audiolarni start vaqti bo'yicha videoga biriktirish."""
    inputs: list[str] = ["-i", str(silent_video)]
    filters: list[str] = []
    labels: list[str] = []

    for position, (cue, audio_path) in enumerate(tracks, start=1):
        inputs += ["-i", str(audio_path)]
        label = f"a{position}"
        filters.append(f"[{position}:a]adelay=delays={cue.start_ms}:all=1[{label}]")
        labels.append(f"[{label}]")

    filters.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0[aout]"
    )
    filter_script = ";\n".join(filters)

    # Subtitrlar ko'p bo'lganda filtr matni juda uzayadi, shuning uchun fayldan o'qitamiz.
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        handle.write(filter_script)
        script_path = Path(handle.name)

    try:
        run_ffmpeg(
            [
                *inputs,
                "-filter_complex_script",
                str(script_path),
                "-map",
                "0:v",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(output),
            ],
            f"yakuniy video yig'ilmoqda -> {output.name}",
        )
    finally:
        script_path.unlink(missing_ok=True)


# --- Asosiy oqim -------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print(" Video tarjimon: ingliz -> o'zbek (aisha-ai + ffmpeg)")
    print("=" * 60)

    if shutil.which("ffmpeg") is None:
        fail("ffmpeg topilmadi. Uni o'rnating: brew install ffmpeg")

    # 1-bosqich
    video = ask_video_path()
    srt_path = video.with_suffix(".srt")
    uz_srt_path = video.with_name(f"{video.stem}-uz.srt")
    audios_dir = video.parent / "audios"
    output_video = video.with_name(f"{video.stem}-uz{video.suffix}")

    # 2-bosqich
    print("\n[2/7] Videodan audio ajratilmoqda...")
    audio_path = extract_audio(video)
    print(f"  Tayyor: {audio_path}")

    # 3-bosqich (qo'lda bajariladi)
    print("\n[3/7] Transkripsiya (qo'lda bajariladi).")
    print(f"  Kutilayotgan fayl: {srt_path}")
    confirm("  Ingliz tilidagi .srt fayl tayyormi?")
    if not srt_path.is_file():
        fail(f"{srt_path} topilmadi.")

    # 4-bosqich (qo'lda bajariladi)
    print("\n[4/7] Tarjima (qo'lda bajariladi).")
    print(f"  Kutilayotgan fayl: {uz_srt_path}")
    confirm("  O'zbek tilidagi .srt fayl tayyormi?")
    if not uz_srt_path.is_file():
        fail(f"{uz_srt_path} topilmadi.")

    cues = parse_srt(uz_srt_path)
    if not cues:
        fail(f"{uz_srt_path} ichida subtitr topilmadi.")
    print(f"  {len(cues)} ta subtitr o'qildi.")

    # 5-bosqich
    print(f"\n[5/7] aisha-ai orqali audio generatsiya qilinmoqda -> {audios_dir}")
    client = AishaClient(api_key=get_api_key(), language="uz")
    tracks = generate_tts_files(cues, audios_dir, client)
    print(f"  {len(tracks)} ta audio fayl tayyor.")

    # 6-bosqich
    print("\n[6/7] Videoning ovozsiz nusxasi olinmoqda...")
    silent_video = strip_audio(video)
    print(f"  Tayyor: {silent_video}")

    # 7-bosqich
    print("\n[7/7] Audiolar timestamp bo'yicha videoga biriktirilmoqda...")
    mux_audio(silent_video, tracks, output_video)

    print("\n" + "=" * 60)
    print(f" Tayyor! Natija: {output_video}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
