"""4-bosqich: .srt fayldagi matnlarni bir tildan boshqa tilga tarjima qilish.

Tarjima Claude Code'ning **headless** rejimi orqali bajariladi: `claude -p` ga
butun .srt matni prompt sifatida beriladi va u tayyor .srt qaytaradi. Ya'ni bu
bosqich endi qo'lda bajarilmaydi.

Model faqat matn qaytarishi kerak, shuning uchun barcha tool'lar o'chirilgan
(`--disallowed-tools`) va sessiya saqlanmaydi (`--no-session-persistence`).

Promptdagi eng muhim qoida — APOSTROF: tarjima qilinmay qolgan inglizcha so'zga
o'zbekcha qo'shimcha qo'shilsa, u apostrof bilan ajratiladi (`container'lar`,
`docker'ga`). Buning sababi 5-bosqichda: `steps/normalize_srt.py` atamani
chegarasi bo'yicha topadi va apostrof o'sha chegara belgilaridan biri. Agar
tarjimon "containerlar" deb yozib yuborsa, atama topilmay qoladi va TTS uni
o'zbekcha o'qish qoidalari bilan noto'g'ri talaffuz qiladi.

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

# Tarjima rejimlari. Farqi bitta narsada: matnda qancha inglizcha so'z qoladi.
MODE_KEEP_TERMS = 1     # odatiy — atamalar va ismlar inglizcha qoladi
MODE_TRANSLATE_MAX = 2  # imkon qadar ko'proq so'z o'zbekchaga o'giriladi

DEFAULT_MODE = MODE_KEEP_TERMS

# Menyuda ko'rinadigan nomlar.
MODE_LABELS = {
    MODE_KEEP_TERMS: "Atamalar inglizcha qoladi (odatiy)",
    MODE_TRANSLATE_MAX: "Imkon qadar tarjima qilinadi — faqat tarjimasi yo'q so'zlar qoladi",
}

# Har bir rejim promptning birinchi xatboshisiga o'z jumlasini qo'shadi.
MODE_RULES = {
    MODE_KEEP_TERMS: (
        "Texnik atamalar va ismlar tarjima qilinmasdan, asl inglizcha yozuvida qolsin."
    ),
    MODE_TRANSLATE_MAX: (
        "Imkon qadar KO'PROQ so'zni tarjima qil — inglizcha yozuvida faqat AYNAN TARJIMASI "
        "YO'Q so'zlargina qolsin."
    ),
}

# 2-rejim uchun qo'shimcha blok — qaysi so'z inglizcha qolishi aniq chegaralanadi.
MODE_EXTRAS = {
    MODE_KEEP_TERMS: "",
    MODE_TRANSLATE_MAX: """
QAYSI SO'Z INGLIZCHA QOLADI. Faqat ikki toifa:
  1) Atoqli nomlar — brend, kompaniya, mahsulot va loyiha nomlari, odam ismlari, shuningdek fayl, papka, buyruq va kod nomlari (Odoo, Docker, Kubernetes, docker-compose.yml, npm install).
  2) O'zbek tilida muqobili umuman yo'q texnik atamalar.

Boshqa hamma so'z tarjima qilinadi. So'zning o'zbekcha muqobili bor bo'lsa, u qanchalik "texnik" ko'rinmasin, TARJIMA QILINADI.

Atoqli nom yonidagi tavsifiy so'z ham tarjima qilinadi: nomning o'zi inglizcha qoladi, uni tavsiflayotgan so'z esa o'zbekchaga o'giriladi.

    NOTO'G'RI                    TO'G'RI
    Odoo Accounting moduli       Odoo buxgalteriya moduli
    settings sahifasi            sozlamalar sahifasi
    invoice yaratamiz            hisob-faktura yaratamiz
    customerlar ro'yxati         mijozlar ro'yxati
    reportni ochamiz             hisobotni ochamiz

Shubha bo'lsa, tarjima qilish tomonini tanla — inglizcha qoldirish faqat boshqa iloji bo'lmaganda. Ayni paytda sun'iy yoki kam ishlatiladigan so'z o'ylab topma: keng qo'llaniladigan, jonli o'zbekcha so'zni ishlat.
""",
}

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
    "izoh, sarlavha, markdown code fence yoki boshqa qo'shimcha matn yozmaysan. "
    "Asl inglizcha yozuvida qoldirilgan so'zga o'zbekcha qo'shimcha qo'shilsa, "
    "qo'shimchani hamisha apostrof bilan ajratasan: container'lar, docker'ga."
)

# Apostrof qoidasi 5-bosqich uchun ham muhim: `steps/normalize_srt.py` atamani
# faqat chegarasi to'g'ri kelganda almashtiradi, apostrof esa TRAILING_CHARS
# ro'yxatida bor. "containerlar" deb yozilsa atama umuman topilmaydi va TTS uni
# o'zbekcha o'qish qoidalari bilan talaffuz qilib yuboradi.
TRANSLATE_PROMPT = """Yuklangan .srt faylni {language} tarjima qil. Timestamp'lar o'zgarmasin, format saqlansin. Gap yoki atama ikki blokka bo'linib qolgan joylarda bloklarni birlashtirishga ruxsat — birlashgan blok birinchi bo'lakning boshi va oxirgi bo'lakning oxiri vaqtini olsin, keyin qayta raqamla. {mode_rule} Uslub — jonli, o'qituvchi so'zlayotgandek. Transkripsiya xatolarini to'g'irlab tarjima qil. Natijada tarjima qilingan .srt faylni ber.
{mode_extra}
QAT'IY QOIDA — APOSTROF. Tarjima qilinmasdan asl inglizcha yozuvida qoldirilgan so'zga o'zbekcha qo'shimcha qo'shilsa, qo'shimcha APOSTROF (') bilan ajratilishi SHART. Bu qoidadan istisno yo'q.

    NOTO'G'RI              TO'G'RI
    containerlar           container'lar
    dockerga               docker'ga
    kubernetesdan          kubernetes'dan
    imageni                image'ni
    Dockerfileda           Dockerfile'da
    volumening             volume'ning
    containerlarimizni     container'larimizni

Qoida barcha qo'shimchalarga tegishli: kelishik (-ga, -ni, -dan, -da, -ning), ko'plik (-lar), egalik (-im, -ing, -i, -imiz, -ingiz), fe'l va boshqa yasovchilar, hamda ularning birikmalari. Qo'shimcha necha bo'g'inli bo'lishidan qat'i nazar, apostrof faqat BITTA — inglizcha so'z tugagan joyda qo'yiladi.

Apostrof FAQAT inglizcha yozuvida qolgan so'zlarga qo'yiladi. O'zbekcha so'zlarga (kurs, dastur, ilova) qo'shimcha odatdagidek, apostrofsiz yoziladi. Inglizcha so'z qo'shimchasiz kelsa ham apostrof qo'yilmaydi: "docker ishga tushdi".

Javobingda faqat tayyor .srt matni bo'lsin — hech qanday izoh yoki ``` belgisisiz.

Fayl nomi: {name}

--- .SRT BOSHLANISHI ---
{content}
--- .SRT TUGASHI ---"""

FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\n(.*)\n```$", re.DOTALL)


def ask_mode() -> int:
    """Tarjima rejimini so'rash. Bo'sh Enter bosilsa, odatiy rejim olinadi."""
    print("\nTarjima rejimi:")
    for number, label in MODE_LABELS.items():
        print(f"  [{number}]  {label}")

    while True:
        answer = input(f"Rejimni tanlang (1-{len(MODE_LABELS)}) [{DEFAULT_MODE}]: ").strip()
        if not answer:
            return DEFAULT_MODE
        if answer.isdigit() and int(answer) in MODE_LABELS:
            return int(answer)
        print(f"  1 dan {len(MODE_LABELS)} gacha bo'lgan raqamni kiriting.")


def translate_srt(
    srt_path: str | Path | None = None,
    translated_srt_path: str | Path | None = None,
    src_language: str = DEFAULT_SRC_LANGUAGE,
    dst_language: str = DEFAULT_DST_LANGUAGE,
    redo: bool | None = None,
    mode: int | None = None,
) -> Path:
    """.srt ni tarjima qilib, natija faylning manzilini qaytarish.

    Batafsil natija (holat va narx) kerak bo'lsa, `translate_srt_detailed` ni
    ishlating — bu funksiya o'shaning qisqa ko'rinishi.
    """
    path, _status, _cost = translate_srt_detailed(
        srt_path, translated_srt_path, src_language, dst_language, redo, mode
    )
    return path


def translate_srt_detailed(
    srt_path: str | Path | None = None,
    translated_srt_path: str | Path | None = None,
    src_language: str = DEFAULT_SRC_LANGUAGE,
    dst_language: str = DEFAULT_DST_LANGUAGE,
    redo: bool | None = None,
    mode: int | None = None,
) -> tuple[Path, str, float]:
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
        mode: Tarjima rejimi — 1 (atamalar inglizcha qoladi) yoki 2 (imkon qadar
            tarjima qilinadi). `None` bo'lsa, input orqali so'raladi. Boshqa
            koddan chaqirilganda aniq qiymat bering.

    Returns:
        (manzil, holat, narx) — holat "ok" yoki "skipped" (mavjud fayl ishlatildi),
        narx esa shu chaqiruvga ketgan dollar (o'tkazib yuborilganda 0.0).
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
            return translated_srt_path, "skipped", 0.0

    # Rejim tayyor natija tekshiruvidan KEYIN so'raladi — fayl allaqachon bor
    # bo'lsa, foydalanuvchini keraksiz savol bilan bezovta qilmaymiz.
    if mode is None:
        mode = ask_mode()
    if mode not in MODE_RULES:
        fail(f"Noma'lum rejim: {mode}. Faqat {list(MODE_RULES)} qabul qilinadi.")

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
        mode_rule=MODE_RULES[mode],
        mode_extra=MODE_EXTRAS[mode],
        name=srt_path.name,
        content=srt_path.read_text(encoding="utf-8-sig"),
    )

    print(f"  Rejim: {mode} — {MODE_LABELS[mode]}")
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
    return translated_srt_path, "ok", cost


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
