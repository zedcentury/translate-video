#!/usr/bin/env python3
"""Diktofon yozuvidagi fon shovqini va keraksiz ovozlarni tozalash.

Voice Recorder bilan yozib olingan yozuvda odatda nutq bilan birga xona shovqini,
konditsioner gujillashi, ko'chadagi ovozlar, klaviatura tovushi va shunga
o'xshash keraksiz tovushlar bo'ladi. Bu skript ana shu qatlamlarni olib tashlab,
faqat gapirgan odam ovozini qoldiradi.

`steps/remove_vocals.py` ning aynan TESKARISI: u demucs ajratgan ikki oqimdan
fonni (`no_vocals`) oladi, bu yerda esa nutqning o'zi (`vocals`) olinadi.

Ish tartibi:
    1. yozuvdan 44.1 kHz stereo audio ajratiladi (demucs shu formatni kutadi);
    2. demucs `--two-stems=vocals` bilan nutqni fondan ajratadi;
    3. ixtiyoriy ravishda ffmpeg filtri qo'llanadi — past chastotali guvillash
       olib tashlanadi, qolgan shitirlash bosiladi va ovoz darajasi tenglanadi;
    4. natija so'ralgan formatda saqlanadi (kengaytmasiga qarab wav/mp3/m4a).

Demucs nimani uddalaydi va nimani yo'q:

    + musiqa, televizor, transport, konditsioner, ventilyator shovqini
    + klaviatura, taqillash kabi qisqa tovushlar
    + doimiy shitirlash (qisman — qoldig'ini ffmpeg filtri oladi)
    - YONIDAGI ODAMNING GAPI — u ham "vocals" hisoblanadi va joyida qoladi
    - kuchli aks-sado (reverb) — demucs uni nutqning bir qismi deb biladi

Ya'ni demucs "shovqin tozalagich" emas, "nutqni ajratgich" — lekin amalda
diktofon yozuvlari uchun oddiy shovqin filtrlaridan ancha yaxshi natija beradi,
chunki u nutqni chastota bo'yicha emes, MAZMUN bo'yicha ajratadi.

Muhim: model musiqa yozuvlarida (MUSDB18) o'rgatilgan, shuning uchun ba'zan
nutq chetlarini "yeb" qo'yadi yoki ovozga biroz "suv ostida" tusi beradi. Sifat
yetarli bo'lmasa, avval `POLISH` ni o'chirib ko'ring — aybdor ko'pincha
qo'shimcha filtr bo'ladi.

O'rnatish:
    pip install demucs

Ikki xil ishlatiladi:

    # 1) Faylning o'zini ishga tushirganda — manzillar input orqali so'raladi
    python utils/clean_audio.py

    # 2) Boshqa koddan chaqirganda — argument bilan, hech narsa so'ralmaydi
    from utils.clean_audio import clean_audio
    clean_audio("yozuv.m4a", "yozuv-tozalangan.wav")

Environment o'zgaruvchilari:
    DEMUCS_MODEL   — model nomi (default: htdemucs)
    DEMUCS_DEVICE  — cpu / cuda / mps (default: cuda bo'lsa cuda, aks holda cpu)
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.remove_vocals import CHANNELS, DEMUCS_MODEL, SAMPLE_RATE, run_demucs  # noqa: E402
from utils.common import ask_path, ask_yes_no, fail, format_duration, run_ffmpeg  # noqa: E402

# Natijaviy fayl nomiga qo'shiladigan qo'shimcha: yozuv -> yozuv-tozalangan
OUTPUT_SUFFIX = "-tozalangan"

# Manzil so'ralganda taklif qilinadigan kengaytma.
DEFAULT_EXTENSION = ".wav"

# Demucs'dan keyingi qo'shimcha tozalash zanjiri:
#   highpass=f=80    — 80 Hz dan pastdagi guvillash va mikrofonni ushlash tovushi
#                      (nutqning eng past chastotasi ~85 Hz dan boshlanadi)
#   afftdn=nf=-25    — demucs qoldirgan shitirlashni FFT orqali bosish
#   loudnorm         — ovoz darajasini bir tekisda tenglash (podkast me'yori)
POLISH_FILTER = "highpass=f=80,afftdn=nf=-25,loudnorm=I=-18:TP=-2:LRA=11"

# Natija mono qilib yoziladi: diktofon yozuvi baribir bitta odamning ovozi,
# stereo esa faylni ikki barobar kattalashtiradi va hech narsa qo'shmaydi.
OUTPUT_CHANNELS = 1

# Chastota aniq ko'rsatiladi: `loudnorm` filtri ichida 192 kHz da hisoblaydi va
# ko'rsatilmasa natijani ham o'sha chastotada yozib yuboradi — fayl sababsiz
# to'rt barobar kattalashadi.
OUTPUT_SAMPLE_RATE = SAMPLE_RATE


def clean_audio(
    source_path: str | Path | None = None,
    output_path: str | Path | None = None,
    polish: bool | None = None,
    model: str = DEMUCS_MODEL,
) -> Path:
    """Yozuvdan fon shovqinini olib tashlab, faqat nutq qolgan fayl yaratish.

    Args:
        source_path: Tozalanadigan yozuv (audio yoki video). Berilmasa, input
            orqali so'raladi.
        output_path: Natija qayerga saqlansin. Berilmasa, input orqali so'raladi
            (default: `<nom>-tozalangan.wav`). Format kengaytmadan aniqlanadi.
        polish: Demucs'dan keyin qo'shimcha ffmpeg filtri qo'llansinmi. `None` —
            so'raladi, `True` — qo'llanadi, `False` — demucs natijasi o'zgarishsiz
            qoladi. Boshqa koddan chaqirilganda aniq qiymat bering, aks holda
            quvur o'rtasida savol berilib qoladi.
        model: Demucs modeli (default: htdemucs).

    Returns:
        Yaratilgan faylning manzili.
    """
    if source_path is None:
        source_path = ask_path(
            "1) Tozalanadigan yozuv manzili (/path/to/yozuv.m4a)", must_exist=True
        )
    source_path = Path(source_path).expanduser().resolve()
    if not source_path.is_file():
        fail(f"Yozuv topilmadi: {source_path}")

    if output_path is None:
        output_path = ask_path(
            "2) Tozalangan yozuv qayerga saqlansin",
            default=source_path.with_name(
                f"{source_path.stem}{OUTPUT_SUFFIX}{DEFAULT_EXTENSION}"
            ),
        )
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path == source_path:
        fail("Natija manba yozuv bilan bir xil bo'lishi mumkin emas.")

    if polish is None:
        polish = ask_yes_no(
            "3) Qo'shimcha filtr qo'llansinmi (guvillash + shitirlash + ovoz darajasi)",
            default=True,
        )

    started = time.monotonic()
    print(f"  Manba: {source_path.name}")

    # Barcha oraliq fayllar vaqtinchalik papkada — natijadan boshqa hech narsa qolmaydi.
    with tempfile.TemporaryDirectory() as workdir:
        stereo_audio = Path(workdir) / "manba-44k.wav"
        run_ffmpeg(
            [
                "-i", str(source_path),
                "-vn",
                "-ar", str(SAMPLE_RATE),
                "-ac", str(CHANNELS),
                str(stereo_audio),
            ],
            f"demucs uchun audio tayyorlanmoqda ({SAMPLE_RATE} Hz stereo)",
        )

        # `stem="vocals"` — remove_vocals.py dan farqi shu yerda: u fonni oladi,
        # biz esa nutqni olamiz.
        speech = run_demucs(stereo_audio, Path(workdir) / "demucs", model, stem="vocals")

        # Demucs natijasi 44.1 kHz stereo — uni so'ralgan formatga o'tkazamiz.
        arguments = ["-i", str(speech)]
        if polish:
            arguments += ["-af", POLISH_FILTER]
        arguments += [
            "-ar", str(OUTPUT_SAMPLE_RATE),
            "-ac", str(OUTPUT_CHANNELS),
            str(output_path),
        ]

        description = "natija yozilmoqda" if not polish else "filtr qo'llanib, natija yozilmoqda"
        run_ffmpeg(arguments, f"{description} -> {output_path.name}")

    print(f"  Tayyor: {output_path} ({size_of(output_path)})")
    print(f"  Sarflangan vaqt: {format_duration(time.monotonic() - started)}")
    return output_path


def size_of(path: Path) -> str:
    """Fayl hajmini o'qishga qulay ko'rinishda qaytarish."""
    megabytes = path.stat().st_size / (1024 * 1024)
    return f"{megabytes:.1f} MB"


if __name__ == "__main__":
    if shutil.which("ffmpeg") is None:
        fail("ffmpeg topilmadi. O'rnating: brew install ffmpeg")
    try:
        clean_audio()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
