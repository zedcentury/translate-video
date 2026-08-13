"""1-bosqich: videodan audio qismini butunlay olib tashlash (ovozsiz video).

Kurslarda orqa fondagi ovoz (musiqa, effektlar) odatda kerak emas — shuning
uchun nutqni fondan ajratish (demucs) o'rniga audio oqimi umuman olib
tashlanadi. Natijada ovozsiz video qoladi, 7-bosqich uning ustiga o'zbekcha
audiolarni qo'yadi.

Qo'lda qilinganda bu shunga teng:
    ffmpeg -i docker9.mp4 -an -c:v copy docker9-no-audio.mp4

Video oqimi qayta kodlanmaydi (`-c:v copy`), shuning uchun tez ishlaydi va
sifat yo'qolmaydi.
"""

from __future__ import annotations

from pathlib import Path

from utils import ask_path, fail, run_ffmpeg

# Ovozsiz video fayl nomiga qo'shiladigan qo'shimcha: docker9 -> docker9-no-audio
OUTPUT_SUFFIX = "-no-audio"


def remove_audio(
    video_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> Path:
    """Videoning audio qismini olib tashlab, ovozsiz video yaratish.

    Args:
        video_path: Manba video fayl manzili. Berilmasa, input orqali so'raladi.
        output_path: Natijaviy ovozsiz video manzili. Berilmasa, input orqali
            so'raladi (default qiymat: `<nom>-no-audio.<kengaytma>`).

    Returns:
        Yaratilgan ovozsiz videoning manzili.
    """
    if video_path is None:
        video_path = ask_path("Video fayl manzilini kiriting (/path/to/docker/docker.mp4)", must_exist=True)
    video_path = Path(video_path).expanduser().resolve()
    if not video_path.is_file():
        fail(f"Video fayl topilmadi: {video_path}")

    if output_path is None:
        output_path = ask_path(
            "Ovozsiz video qayerga saqlansin",
            default=video_path.with_name(f"{video_path.stem}{OUTPUT_SUFFIX}{video_path.suffix}"),
        )
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path == video_path:
        fail("Natija manba video bilan bir xil bo'lishi mumkin emas.")

    run_ffmpeg(
        [
            "-i", str(video_path),
            "-an",              # audio oqimini butunlay tashlab ketish
            "-c:v", "copy",     # tasvir qayta kodlanmaydi
            str(output_path),
        ],
        f"audio olib tashlanmoqda -> {output_path.name}",
    )
    return output_path


if __name__ == "__main__":
    result = remove_audio()
    print(f"Tayyor: {result}")
