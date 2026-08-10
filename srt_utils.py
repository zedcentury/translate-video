"""SRT fayllarni o'qish/yozish uchun umumiy yordamchilar.

2-, 3- va 4-bosqichlar shu modulga tayanadi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TIMESTAMP_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


@dataclass
class Cue:
    """SRT faylning bitta bloki."""

    index: int
    start_ms: int
    end_ms: int
    text: str

    @property
    def slug(self) -> str:
        """Boshlanish vaqtidan audio fayl nomi: 00:01:02,500 -> 00-01-02-500

        `:` va `,` belgilari fayl nomida muammo tug'dirgani uchun `-` ishlatiladi.
        5-bosqich audio fayl nomini aynan shu formatda kutadi.
        """
        return ms_to_slug(self.start_ms)


def to_ms(hours: str | int, minutes: str | int, seconds: str | int, millis: str | int) -> int:
    """Vaqt qismlarini millisekundga aylantirish."""
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1000
        + int(str(millis).ljust(3, "0"))
    )


def ms_to_slug(total_ms: int) -> str:
    """Millisekundni fayl nomiga mos ko'rinishga aylantirish: 62500 -> 00-01-02-500"""
    total, millis = divmod(total_ms, 1000)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}-{minutes:02d}-{seconds:02d}-{millis:03d}"


def ms_to_timestamp(total_ms: int) -> str:
    """Millisekundni SRT formatiga aylantirish: 62500 -> 00:01:02,500"""
    total, millis = divmod(total_ms, 1000)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


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
            print(f"  [ogohlantirish] vaqt qatori yo'q blok tashlab ketildi: {lines[0][:40]!r}")
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


def write_srt(cues: list[Cue], path: Path) -> Path:
    """Cue ro'yxatini SRT faylga yozish."""
    blocks = [
        f"{position}\n"
        f"{ms_to_timestamp(cue.start_ms)} --> {ms_to_timestamp(cue.end_ms)}\n"
        f"{cue.text}\n"
        for position, cue in enumerate(cues, start=1)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path
