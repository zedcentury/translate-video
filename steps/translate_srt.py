"""4-bosqich: .srt fayldagi matnlarni bir tildan boshqa tilga tarjima qilish.

Tarjima Claude Code'ning **headless** rejimi orqali bajariladi: `claude -p` ga
butun .srt matni prompt sifatida beriladi va u tayyor .srt qaytaradi. Ya'ni bu
bosqich endi qo'lda bajarilmaydi.

Model faqat matn qaytarishi kerak, shuning uchun barcha tool'lar o'chirilgan
(`--disallowed-tools`) va sessiya saqlanmaydi (`--no-session-persistence`).

Talab: `claude` CLI o'rnatilgan va tizimga kirilgan bo'lishi kerak.

Environment o'zgaruvchilari:
    CLAUDE_MODEL    — model nomi (default: claude-opus-5)
    CLAUDE_EFFORT   — effort darajasi (default: high)
    CLAUDE_TIMEOUT  — bitta chaqiruv uchun sekund (default: 3600)

Ishga tushirish (loyiha ildizidan):
    python steps/translate_srt.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.common import ask_path, ask_yes_no, fail, format_duration  # noqa: E402
from utils.srt import parse_srt  # noqa: E402

DEFAULT_SRC_LANGUAGE = "en"
DEFAULT_DST_LANGUAGE = "uz"

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
EFFORT = os.environ.get("CLAUDE_EFFORT", "high")

# Tarjima qilinadigan fayllar uzun bo'lgani uchun bitta chaqiruvga katta limit kerak.
TIMEOUT_SEC = int(os.environ.get("CLAUDE_TIMEOUT", "3600"))

# Til kodini promptda tabiiy ko'rinishga o'tkazish uchun.
LANGUAGE_NAMES = {
    "uz": "o'zbek tiliga (lotin)",
    "en": "ingliz tiliga",
    "ru": "rus tiliga",
    "tr": "turk tiliga",
}

SYSTEM_PROMPT = (
    "Sen professional subtitr tarjimonisan. Faqat so'ralgan .srt matnini qaytarasan: "
    "izoh, sarlavha, markdown code fence yoki boshqa qo'shimcha matn yozmaysan."
)

TRANSLATE_PROMPT = """Yuklangan .srt faylni {language} tarjima qil. Timestamp'lar o'zgarmasin, format saqlansin. Gap yoki atama ikki blokka bo'linib qolgan joylarda bloklarni birlashtirishga ruxsat — birlashgan blok birinchi bo'lakning boshi va oxirgi bo'lakning oxiri vaqtini olsin, keyin qayta raqamla. Texnik atamalar va ismlar tarjima qilinmasdan, asl inglizcha yozuvida qolsin. Uslub — jonli, o'qituvchi so'zlayotgandek. Transkripsiya xatolarini to'g'irlab tarjima qil. Natijada tarjima qilingan .srt faylni ber.

Javobingda faqat tayyor .srt matni bo'lsin — hech qanday izoh yoki ``` belgisisiz.

Fayl nomi: {name}

--- .SRT BOSHLANISHI ---
{content}
--- .SRT TUGASHI ---"""

FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\n(.*)\n```$", re.DOTALL)


def translate_srt(
    srt_path: str | Path | None = None,
    translated_srt_path: str | Path | None = None,
    src_language: str = DEFAULT_SRC_LANGUAGE,
    dst_language: str = DEFAULT_DST_LANGUAGE,
    redo: bool | None = None,
) -> Path:
    """.srt fayldagi matnlarni tarjima qilib, yangi .srt fayl yaratish.

    Args:
        srt_path: Manba .srt fayl manzili. Berilmasa, input orqali so'raladi.
        translated_srt_path: Natijaviy .srt fayl manzili. Berilmasa, input orqali
            so'raladi (default qiymat: `<nom>-<dst_language>.srt`).
        src_language: Manba til (default: "en").
        dst_language: Tarjima tili (default: "uz").
        redo: Tarjima allaqachon mavjud bo'lsa nima qilish kerak. `None` — so'raladi,
            `True` — qaytadan tarjima qilinadi, `False` — mavjud fayl ishlatiladi.
            Boshqa koddan chaqirilganda aniq qiymat bering, aks holda quvur
            o'rtasida savol berilib qoladi.

    Returns:
        Tarjima qilingan .srt faylning manzili.
    """
    if srt_path is None:
        srt_path = ask_path("Tarjima qilinadigan .srt fayl manzilini kiriting", must_exist=True)
    srt_path = Path(srt_path).expanduser().resolve()
    if not srt_path.is_file():
        fail(f".srt fayl topilmadi: {srt_path}")

    if translated_srt_path is None:
        translated_srt_path = ask_path(
            "Tarjima qilingan .srt fayl qayerga saqlansin",
            default=srt_path.with_name(f"{srt_path.stem}-{dst_language}.srt"),
        )
    translated_srt_path = Path(translated_srt_path).expanduser().resolve()
    translated_srt_path.parent.mkdir(parents=True, exist_ok=True)

    if translated_srt_path == srt_path:
        fail("Tarjima manba fayl ustiga yozilishi mumkin emas.")

    # Tarjima pullik va sekin — tayyor natija bo'lsa, qaytadan so'ramaymiz.
    if is_ready(translated_srt_path):
        if redo is None:
            redo = ask_yes_no(
                f"  {translated_srt_path.name} allaqachon mavjud. Qaytadan tarjima qilinsinmi?",
                default=False,
            )
        if not redo:
            print("  Mavjud fayl ishlatildi.")
            return translated_srt_path

    if shutil.which("claude") is None:
        fail(
            "claude CLI topilmadi. O'rnating: npm install -g @anthropic-ai/claude-code\n"
            "So'ng `claude` ni bir marta ishga tushirib, tizimga kiring."
        )

    cues = parse_srt(srt_path)
    if not cues:
        fail(f"{srt_path} ichida subtitr topilmadi.")

    language = LANGUAGE_NAMES.get(dst_language.lower(), f"{dst_language} tiliga")
    prompt = TRANSLATE_PROMPT.format(
        language=language,
        name=srt_path.name,
        content=srt_path.read_text(encoding="utf-8-sig"),
    )

    print(f"  Yo'nalish: {src_language} -> {dst_language} | {len(cues)} ta subtitr")
    print(f"  Model: {MODEL} (effort={EFFORT}) — bu biroz vaqt oladi...")

    started_at = time.monotonic()
    text, cost = run_claude(prompt)
    translated_srt_path.write_text(strip_fence(text), encoding="utf-8")

    translated = parse_srt(translated_srt_path)
    if not translated:
        translated_srt_path.unlink(missing_ok=True)
        fail("Model qaytargan matn .srt formatiga o'xshamaydi — fayl saqlanmadi.")

    print(
        f"  {len(translated)} ta subtitr yozildi "
        f"({format_duration(time.monotonic() - started_at)}, ${cost:.4f})."
    )
    if len(translated) > len(cues):
        print(
            f"  [ogohlantirish] tarjimada bloklar ko'paydi ({len(cues)} -> {len(translated)}), "
            f"faylni ko'zdan kechiring."
        )
    return translated_srt_path


def run_claude(prompt: str) -> tuple[str, float]:
    """Claude Code'ni headless (-p) rejimda ishga tushirib, (matn, narx) qaytarish."""
    cmd = [
        "claude",
        "-p",
        "--model", MODEL,
        "--effort", EFFORT,
        "--output-format", "json",
        "--system-prompt", SYSTEM_PROMPT,
        "--no-session-persistence",
        # Tarjima uchun hech qanday tool kerak emas — faqat matn qaytsin.
        "--disallowed-tools",
        "Bash Read Write Edit Glob Grep WebFetch WebSearch Task NotebookEdit",
    ]
    try:
        process = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
            cwd=ROOT,
        )
    except subprocess.TimeoutExpired:
        fail(f"claude {TIMEOUT_SEC} sekundda javob bermadi (CLAUDE_TIMEOUT bilan oshiring).")

    # Xatolikda ham JSON qaytadi va undagi `result` odam o'qiydigan xabar bo'ladi,
    # shuning uchun avval javobni o'qishga urinamiz.
    payload = None
    if process.stdout.strip():
        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError:
            payload = None

    if payload is None:
        detail = (process.stderr or process.stdout).strip()[:500]
        fail(f"claude javobini o'qib bo'lmadi (code={process.returncode}): {detail}")

    if payload.get("is_error") or process.returncode != 0:
        message = str(payload.get("result") or payload.get("error") or "").strip()
        fail(f"claude xatolik bilan tugadi (code={process.returncode}): {message[:500]}")

    result = payload.get("result") or ""
    if not result.strip():
        fail("model bo'sh javob qaytardi.")

    return result, float(payload.get("total_cost_usd") or 0.0)


def strip_fence(text: str) -> str:
    """Model baribir ``` bilan o'rab yuborsa, uni tozalash."""
    text = text.strip()
    match = FENCE_RE.match(text)
    if match:
        text = match.group(1).strip()
    return text + "\n"


def is_ready(path: Path) -> bool:
    """Fayl mavjud va bo'sh emasmi."""
    return path.is_file() and path.stat().st_size > 0


if __name__ == "__main__":
    result = translate_srt()
    print(f"Tayyor: {result}")
