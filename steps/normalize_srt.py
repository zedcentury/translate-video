"""5-bosqich: tarjima qilingan .srt dagi matnlarni TTS uchun normalize qilish.

Ikki amal SHU TARTIBDA bajariladi:

1. ATAMALAR ALMASHTIRILADI (terms.json). Tarjima qilinmaydigan inglizcha
   atamalar TTS tomonidan noto'g'ri o'qiladi, shuning uchun ularni o'zbekcha
   talaffuziga yaqin ko'rinishga o'tkazamiz:

       docker      -> do'ker
       kubernetes  -> kubernites

2. `uztts.normalize` (navoiy-tts ichida) sonlar, sanalar, vaqt va o'lchov
   birliklarini o'qiladigan so'zlarga aylantiradi:

       "Bugun 16.07.2026, soat 14:30 da uchrashamiz."
       -> "Bugun o'n olti iyul ikki ming yigirma olti, soat o'n to'rt o'ttiz da uchrashamiz."

   Almashtirish avval bajarilgani uchun atamaning natijasi (masalan "si-pi-yu 2")
   ham normalize'dan o'tadi va undagi sonlar so'zga aylanadi.

Atamalar ro'yxati alohida JSON faylda saqlanadi va manzili input orqali so'raladi.
Manzil kiritilmasa (Enter), almashtirish bosqichi o'tkazib yuboriladi.

JSON fayl ko'rinishi (namuna: terms.example.json):

    {
      "docker": "do'ker",
      "kubernetes": "kubernites"
    }

ALMASHTIRISH QOIDASI: atama faqat IKKI TOMONIDA HAM BO'SHLIQ bo'lgandagina
almashtiriladi (matn boshi va oxiri ham bo'shliq deb qaraladi). Boshqa hech qanday
holatda tegilmaydi:

    "docker run"      -> almashadi
    "docker."         -> TEGILMAYDI (o'ngida nuqta)
    "docker'ni"       -> TEGILMAYDI (o'ngida apostrof)
    "dockerfile"      -> TEGILMAYDI

Ya'ni JSON dagi kalit matndagi so'zning AYNAN o'zi bo'lishi kerak. Nuqta/vergul
oldidagi yoki qo'shimchali shakllarni ham almashtirmoqchi bo'lsangiz, o'sha
shakllarni ("docker'ni", "docker.") alohida kalit qilib qo'shing.
Katta-kichik harfga qaralmaydi.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.common import ask_optional_path, ask_path, fail  # noqa: E402
from utils.srt import Cue, parse_srt, write_srt  # noqa: E402

NAVOIY_DIR = Path(os.environ.get("NAVOIY_DIR", ROOT / "navoiy-tts"))

# `infer` — sonlar/sanalar/vaqtni so'zga aylantiradi (TTS uchun aynan shu kerak).
# `train` — matnni deyarli o'zgarishsiz qoldiradi.
NORMALIZE_MODE = "infer"


def normalize_srt(
    srt_path: str | Path | None = None,
    output_path: str | Path | None = None,
    replacements_path: str | Path | None = None,
    ask_replacements: bool = True,
) -> Path:
    """Tarjima qilingan .srt matnlarini normalize qilib, yangi .srt yaratish.

    Args:
        srt_path: Tarjima qilingan .srt fayl manzili. Berilmasa, input orqali so'raladi.
        output_path: Natijaviy .srt fayl manzili. Berilmasa, input orqali so'raladi
            (default qiymat: `<nom>-normalized.srt`).
        replacements_path: Atamalar ro'yxati (JSON). Berilmasa, input orqali so'raladi;
            u yerda ham bo'sh qoldirilsa, almashtirish bajarilmaydi.
        ask_replacements: `False` bo'lsa, atamalar fayli so'ralmaydi — `replacements_path`
            berilmagan bo'lsa, shunchaki almashtirishsiz davom etadi. Batch rejimida
            savol berilib qolmasligi uchun kerak.

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

    if replacements_path is None and ask_replacements:
        replacements_path = ask_optional_path(
            "Atamalar JSON fayli manzilini kiriting (/path/to/docker/terms.json)"
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
        # 1) terms.json qoidalari, 2) undan keyin uztts.normalize.
        text = replace_terms(cue.text, pattern, replacements)
        text = normalize(text, mode=NORMALIZE_MODE)
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
    """Atamalarni FAQAT ikki tomonida bo'shliq bo'lgan holda topadigan regex yasash.

    `(?<= )` va `(?= )` — bo'shliqni "iste'mol qilmaydigan" tekshiruvlar, shuning
    uchun yonma-yon turgan ikkita atama ham (`docker run`) ikkalasi almashadi.
    """
    if not replacements:
        return None
    # ENG UZUNIDAN boshlab tartiblaymiz — regex alternatsiyasida Python birinchi
    # mos kelgan variantni oladi, eng uzunini emas. Aks holda "docker compose"
    # o'rniga faqat "docker" almashib, qolgan qismi tegilmay qolardi.
    terms = sorted(replacements, key=len, reverse=True)
    return re.compile(r"(?<= )(?:" + "|".join(re.escape(term) for term in terms) + r")(?= )", re.IGNORECASE)


def replace_terms(text: str, pattern: re.Pattern[str] | None, replacements: dict[str, str]) -> str:
    """Matndagi atamalarni terms.json bo'yicha almashtirish.

    Matn boshi va oxiri ham bo'shliq deb qaraladi — shuning uchun matnni vaqtincha
    bo'shliq bilan o'rab olamiz va oxirida o'sha ikki bo'shliqni olib tashlaymiz.
    """
    if pattern is None:
        return text
    padded = pattern.sub(lambda match: replacements[match.group(0).lower()], f" {text} ")
    return padded[1:-1]


if __name__ == "__main__":
    result = normalize_srt()
    print(f"Tayyor: {result}")
