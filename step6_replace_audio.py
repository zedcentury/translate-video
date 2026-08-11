"""6-bosqich: videoning audio qismini nutqsiz fon audiosiga almashtirish.

5-bosqichda demucs ajratib bergan `<nom>-background.wav` faylini videoga
yagona audio oqim sifatida joylashtiradi. Ya'ni natijaviy videoda inglizcha
nutq umuman qolmaydi — faqat musiqa, effektlar va boshqa fon tovushlari.

7-bosqich shu video ustiga o'zbekcha audiolarni qo'yadi.

Video oqimi qayta kodlanmaydi (`-c:v copy`), shuning uchun tez ishlaydi va
sifat yo'qolmaydi.
"""

from __future__ import annotations

from pathlib import Path

from utils import ask_path, fail, run_ffmpeg

AUDIO_CODEC = "aac"
AUDIO_BITRATE = "192k"


def replace_audio(
    video_path: str | Path | None = None,
    background_audio: str | Path | None = None,
    output_path: str | Path | None = None,
) -> Path:
    """Videoning ovozini fon audiosiga almashtirib, yangi video yaratish.

    Args:
        video_path: Manba video fayl manzili. Berilmasa, input orqali so'raladi.
        background_audio: Nutqsiz fon audiosi (5-bosqich natijasi). Berilmasa,
            input orqali so'raladi (default: `<nom>-background.wav`).
        output_path: Natijaviy video manzili. Berilmasa, input orqali so'raladi
            (default: `<nom>-background.<kengaytma>`).

    Returns:
        Yaratilgan videoning manzili.
    """
    if video_path is None:
        video_path = ask_path("Video fayl manzilini kiriting", must_exist=True)
    video_path = Path(video_path).expanduser().resolve()
    if not video_path.is_file():
        fail(f"Video fayl topilmadi: {video_path}")

    if background_audio is None:
        background_audio = ask_path(
            "Fon audiosi manzilini kiriting",
            default=video_path.with_name(f"{video_path.stem}-background.wav"),
            must_exist=True,
        )
    background_audio = Path(background_audio).expanduser().resolve()
    if not background_audio.is_file():
        fail(f"Fon audiosi topilmadi: {background_audio}")

    if output_path is None:
        output_path = ask_path(
            "Natijaviy video qayerga saqlansin",
            default=video_path.with_name(f"{video_path.stem}-background{video_path.suffix}"),
        )
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_ffmpeg(
        [
            "-i", str(video_path),
            "-i", str(background_audio),
            "-map", "0:v",      # videoning tasvir oqimi
            "-map", "1:a",      # asl ovoz o'rniga fon audiosi
            "-c:v", "copy",
            "-c:a", AUDIO_CODEC,
            "-b:a", AUDIO_BITRATE,
            str(output_path),
        ],
        f"ovoz fon audiosiga almashtirilmoqda -> {output_path.name}",
    )
    return output_path


if __name__ == "__main__":
    result = replace_audio()
    print(f"Tayyor: {result}")
