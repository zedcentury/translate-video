"""4-bosqich: tarjima qilingan .srt dagi matnlarni TTS uchun normalize qilish.

`uztts.normalize` (navoiy-tts ichida) sonlar, sanalar, vaqt va o'lchov birliklarini
o'qiladigan so'zlarga aylantiradi:

    "Bugun 16.07.2026, soat 14:30 da uchrashamiz."
    -> "Bugun o'n olti iyul ikki ming yigirma olti, soat o'n to'rt o'ttiz da uchrashamiz."

Undan keyin ixtiyoriy ravishda ATAMALAR ALMASHTIRILADI. Tarjima qilinmaydigan
inglizcha atamalar TTS tomonidan noto'g'ri o'qilishi mumkin, shuning uchun ularni
o'zbekcha talaffuziga yaqin ko'rinishga o'tkazish kerak bo'ladi:

    docker      -> do'ker
    kubernetes  -> kubernites

Bu ro'yxat alohida JSON faylda saqlanadi va manzili input orqali so'raladi.
Manzil kiritilmasa (Enter), almashtirish bosqichi o'tkazib yuboriladi.

JSON fayl ko'rinishi (namuna: terms.example.json):

    {
      "docker": "do'ker",
      "kubernetes": "kubernites"
    }

Almashtirish katta-kichik harfga qaramaydi va faqat butun so'zlarga qo'llaniladi
("docker" almashadi, "dockerfile" esa tegilmaydi).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from srt_utils import Cue, parse_srt, write_srt
from utils import ask_optional_path, ask_path, fail

ROOT = Path(__file__).resolve().parent
NAVOIY_DIR = Path(os.environ.get("NAVOIY_DIR", ROOT / "navoiy-tts"))

# `infer` — sonlar/sanalar/vaqtni so'zga aylantiradi (TTS uchun aynan shu kerak).
# `train` — matnni deyarli o'zgarishsiz qoldiradi.
NORMALIZE_MODE = "infer"


def normalize_srt(
    srt_path: str | Path | None = None,
    output_path: str | Path | None = None,
    replacements_path: str | Path | None = None,
) -> Path:
    """Tarjima qilingan .srt matnlarini normalize qilib, yangi .srt yaratish.

    Args:
        srt_path: Tarjima qilingan .srt fayl manzili. Berilmasa, input orqali so'raladi.
        output_path: Natijaviy .srt fayl manzili. Berilmasa, input orqali so'raladi
            (default qiymat: `<nom>-normalized.srt`).
        replacements_path: Atamalar ro'yxati (JSON). Berilmasa, input orqali so'raladi;
            u yerda ham bo'sh qoldirilsa, almashtirish bajarilmaydi.

    Returns:
        Normalize qilingan .srt faylning manzili.
    """
    if srt_path is None:
        srt_path = ask_path(
            "Tarjima qilingan .srt fayl manzilini kiriting (/path/to/docker/docker-uz.srt)",
            must_exist=True,
        )
    srt_path = Path(srt_path).expanduser().resolve()
    if not srt_path.is_file():
        fail(f".srt fayl topilmadi: {srt_path}")

    if output_path is None:
        output_path = ask_path(
            "Normalize qilingan .srt qayerga saqlansin",
            default=srt_path.with_name(f"{srt_path.stem}-normalized.srt"),
        )
    output_path = Path(output_path).expanduser().resolve()

    if replacements_path is None:
        replacements_path = ask_optional_path(
            "Atamalar JSON fayli manzilini kiriting (/path/to/docker/normalize.json)"
        )

    replacements = load_replacements(replacements_path)
    if replacements:
        print(f"  {len(replacements)} ta atama almashtiriladi.")
    else:
        print("  Atamalar ro'yxati berilmadi — faqat normalize qilinadi.")

    cues = parse_srt(srt_path)
    if not cues:
        fail(f"{srt_path} ichida subtitr topilmadi.")

    normalize = load_normalizer()
    pattern = build_pattern(replacements)

    changed = 0
    normalized: list[Cue] = []
    for cue in cues:
        text = normalize(cue.text, mode=NORMALIZE_MODE)
        if pattern is not None:
            text = pattern.sub(lambda match: replacements[match.group(0).lower()], text)
        text = re.sub(r"\s+", " ", text).strip()
        if text != cue.text:
            changed += 1
        normalized.append(
            Cue(index=cue.index, start_ms=cue.start_ms, end_ms=cue.end_ms, text=text)
        )

    write_srt(normalized, output_path)
    print(f"  {len(normalized)} ta subtitrdan {changed} tasi o'zgardi -> {output_path.name}")
    return output_path


def load_normalizer():
    """navoiy-tts ichidagi `uztts.normalize` funksiyasini yuklash."""
    if not (NAVOIY_DIR / "uztts").is_dir():
        fail(f"uztts moduli topilmadi: {NAVOIY_DIR / 'uztts'}")
    if str(NAVOIY_DIR) not in sys.path:
        sys.path.insert(0, str(NAVOIY_DIR))

    try:
        from uztts.normalize import normalize
    except ImportError as error:
        fail(f"uztts.normalize import qilinmadi: {error}")
    return normalize


def load_replacements(path: str | Path | None) -> dict[str, str]:
    """JSON fayldan atamalar lug'atini o'qish (kalitlar kichik harfga o'tkaziladi)."""
    if path is None:
        return {}

    path = Path(path).expanduser().resolve()
    if not path.is_file():
        fail(f"Atamalar fayli topilmadi: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"JSON o'qilmadi ({path.name}): {error}")

    if isinstance(data, list):
        # [{"from": "docker", "to": "do'ker"}, ...] ko'rinishi ham qabul qilinadi.
        try:
            data = {item["from"]: item["to"] for item in data}
        except (TypeError, KeyError):
            fail(f"{path.name}: ro'yxat elementlari 'from' va 'to' kalitlariga ega bo'lishi kerak.")
    if not isinstance(data, dict):
        fail(f"{path.name}: JSON obyekt (kalit-qiymat) bo'lishi kerak.")

    return {str(key).strip().lower(): str(value) for key, value in data.items() if str(key).strip()}


def build_pattern(replacements: dict[str, str]) -> re.Pattern[str] | None:
    """Atamalarni butun so'z sifatida topadigan regex yasash."""
    if not replacements:
        return None
    # Uzunlaridan boshlab tartiblaymiz, aks holda "kubernetes api" dan oldin
    # "kubernetes" mos kelib, qolgan qismi almashmay qoladi.
    terms = sorted(replacements, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(term) for term in terms) + r")\b", re.IGNORECASE)


if __name__ == "__main__":
    result = normalize_srt()
    print(f"Tayyor: {result}")
