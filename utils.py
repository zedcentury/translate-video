"""Barcha bosqichlar uchun umumiy yordamchi funksiyalar."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import NoReturn


def fail(message: str) -> NoReturn:
    """Xatolik xabarini chiqarib, dasturni to'xtatish."""
    raise SystemExit(f"\n[XATOLIK] {message}")


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


def ask_path(
    question: str,
    default: str | Path | None = None,
    must_exist: bool = False,
    must_be_dir: bool = False,
) -> Path:
    """Foydalanuvchidan fayl/papka manzilini so'rash.

    Agar `default` berilgan bo'lsa, foydalanuvchi bo'sh Enter bosishi kifoya.
    """
    hint = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{question}{hint}: ").strip().strip("'\"")
        if not raw and default is not None:
            raw = str(default)
        if not raw:
            print("  Manzil kiritilishi shart.")
            continue

        path = Path(raw).expanduser().resolve()
        if must_exist:
            if must_be_dir and not path.is_dir():
                print(f"  Bunday papka topilmadi: {path}")
                continue
            if not must_be_dir and not path.is_file():
                print(f"  Bunday fayl topilmadi: {path}")
                continue
        return path


def ask_text(question: str, default: str) -> str:
    """Matnli qiymat so'rash. Bo'sh Enter bosilsa, default qiymat olinadi."""
    answer = input(f"{question} [{default}]: ").strip()
    return answer or default


def ask_yes_no(question: str, default: bool = True) -> bool:
    """Ha/yo'q savoli — javobni bool ko'rinishida qaytaradi."""
    hint = "[Ha/yo'q]" if default else "[ha/Yo'q]"
    while True:
        answer = input(f"{question} {hint}: ").strip().lower()
        if not answer:
            return default
        if answer in {"ha", "h", "y", "yes", "ok"}:
            return True
        if answer in {"yoq", "yo'q", "n", "no", "q"}:
            return False
        print("  Iltimos 'ha' yoki 'yo'q' deb javob bering.")


def confirm(question: str) -> None:
    """Foydalanuvchi tasdiqlaguncha so'rayveradi; rad etilsa dastur to'xtaydi."""
    while True:
        answer = input(f"{question} [ha/yo'q]: ").strip().lower()
        if answer in {"ha", "h", "y", "yes", "ok", ""}:
            return
        if answer in {"yoq", "yo'q", "n", "no", "q", "exit"}:
            fail("Foydalanuvchi tomonidan bekor qilindi.")
        print("  Iltimos 'ha' yoki 'yo'q' deb javob bering.")
