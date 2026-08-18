#!/usr/bin/env python3
"""kNN-VC: audioning ovozini boshqa ovozga o'tkazadi (voice conversion).

Matn o'zgarmaydi — faqat KIM gapirayotgani o'zgaradi. Ya'ni ikkinchi audiodagi
nutq birinchi audiodagi odamning ovozida qayta yangraydi.

Dastur boshida uch narsa so'raladi:

    1. Namuna audio  — QAYSI ovozga o'tkazamiz (asos/etalon ovoz)
    2. Manba audio   — ovozi o'zgartiriladigan yozuv (matn shundan olinadi)
    3. Natija        — hosil bo'lgan audio qayerga saqlansin

Qanday ishlaydi: WavLM har ikkala yozuvdan xususiyat vektorlarini ajratadi,
so'ng manba audioning har bir kadriga namuna audiodan eng yaqin `topk` ta kadr
topilib, ularning o'rtachasi olinadi (k-nearest neighbors). Natijada HiFiGAN
vokoderi to'lqinni qayta tiklaydi.

Model birinchi chaqiruvda `torch.hub` orqali yuklab olinadi (~1.5 GB:
WavLM-Large + HiFiGAN) va `~/.cache/torch/hub` da saqlanadi.

Muhim: namuna audio qancha uzun bo'lsa (5-10 daqiqa ideal), natija shuncha
yaxshi chiqadi — kNN uchun "tanlov bazasi" katta bo'ladi. Bir necha soniyalik
namunadan sifatli natija kutmang.

Kirish fayllarining chastotasi ahamiyatsiz — kNN-VC o'zi 16 kHz ga keltiradi.
Natija ham 16 kHz mono bo'ladi.

Ikki xil ishlatiladi:

    # 1) Faylning o'zini ishga tushirganda — uchala manzil input orqali so'raladi
    python utils/voice_convert.py

    # 2) Boshqa koddan chaqirganda — argument bilan
    from utils.voice_convert import convert_voice
    convert_voice("namuna.wav", "manba.wav", "natija.wav")

Environment o'zgaruvchilari:
    KNNVC_TOPK    — nechta qo'shni o'rtachalanadi (default: 4)
    KNNVC_DEVICE  — cpu / cuda (default: cuda bo'lsa cuda, aks holda cpu)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# To'g'ridan-to'g'ri ishga tushirilganda loyiha ildizi sys.path da bo'lmaydi.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.common import ask_path, fail, format_duration  # noqa: E402

DEFAULT_TOPK = int(os.environ.get("KNNVC_TOPK", "4"))

# kNN-VC natijani shu chastotada qaytaradi (hifigan/config_v1_wavlm.json).
SAMPLE_RATE = 16000

# Manzil so'ralganda taklif qilinadigan nom.
DEFAULT_OUTPUT_NAME = "converted.wav"

# Model bir marta yuklanadi va shu yerda saqlanadi.
_MODEL = None


def resolve_device() -> str:
    """Qaysi qurilmada hisoblashni aniqlash."""
    forced = os.environ.get("KNNVC_DEVICE")
    if forced:
        return forced

    import torch

    # WavLM CUDA bo'lmasa baribir cpu ga o'tadi (hubconf.py), mps qo'llanmaydi.
    return "cuda" if torch.cuda.is_available() else "cpu"


def load_model(device: str):
    """kNN-VC ni torch.hub orqali bir marta yuklab, keyin qayta ishlatish."""
    global _MODEL
    if _MODEL is None:
        import torch

        print(f"  kNN-VC yuklanmoqda (qurilma: {device})...")
        print("  Birinchi marta ~1.5 GB model yuklab olinadi, bu uzoq davom etadi.")
        _MODEL = torch.hub.load(
            "bshall/knn-vc",
            "knn_vc",
            prematched=True,
            trust_repo=True,
            pretrained=True,
            device=device,
        )
    return _MODEL


def convert_voice(
    reference_path: str | Path | None = None,
    source_path: str | Path | None = None,
    output_path: str | Path | None = None,
    topk: int = DEFAULT_TOPK,
    device: str | None = None,
) -> Path:
    """Manba audioning ovozini namuna audiodagi ovozga o'tkazish.

    Args:
        reference_path: Namuna audio — QAYSI ovozga o'tkaziladi. Berilmasa,
            input orqali so'raladi.
        source_path: Manba audio — ovozi o'zgartiriladigan yozuv (matn shundan
            olinadi). Berilmasa, input orqali so'raladi.
        output_path: Natijaviy .wav fayl manzili. Berilmasa, input orqali
            so'raladi (default: manba fayl yonida `<nom>-converted.wav`).
        topk: kNN dagi qo'shnilar soni (default: 4). Kattaroq qiymat ovozni
            silliqlaydi, lekin talaffuzni xiralashtirishi mumkin.
        device: cpu / cuda. Berilmasa, o'zi aniqlanadi.

    Returns:
        Yaratilgan audio faylning manzili.
    """
    if reference_path is None:
        reference_path = ask_path(
            "1) Namuna audio — qaysi ovozga o'tkazamiz", must_exist=True
        )
    reference_path = Path(reference_path).expanduser().resolve()
    if not reference_path.is_file():
        fail(f"Namuna audio topilmadi: {reference_path}")

    if source_path is None:
        source_path = ask_path(
            "2) Manba audio — ovozi o'zgartiriladigan yozuv", must_exist=True
        )
    source_path = Path(source_path).expanduser().resolve()
    if not source_path.is_file():
        fail(f"Manba audio topilmadi: {source_path}")

    if output_path is None:
        output_path = ask_path(
            "3) Natija qayerga saqlansin",
            default=source_path.with_name(f"{source_path.stem}-converted.wav"),
        )
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path in (reference_path, source_path):
        fail("Natija fayli kirish fayllaridan biri bilan bir xil bo'lishi mumkin emas.")

    import torchaudio

    device = device or resolve_device()
    model = load_model(device)

    started = time.monotonic()
    print(f"  Namuna: {reference_path.name} | manba: {source_path.name} | topk={topk}")

    # Namuna audio — kNN uchun "tanlov bazasi"; manba audio — so'rov ketma-ketligi.
    #
    # Manzil MATN ko'rinishida uzatiladi: kNN-VC ichida `type(path) in [str, Path]`
    # deb tekshiriladi, `Path("x")` esa aslida `PosixPath` bo'lgani uchun bu tekshiruv
    # o'tmay, manzil tensor deb qabul qilinadi va xato beradi.
    matching_set = model.get_matching_set([str(reference_path)])
    query_seq = model.get_features(str(source_path))
    print(f"  Namuna kadrlari: {matching_set.shape[0]} | manba kadrlari: {query_seq.shape[0]}")

    audio = model.match(query_seq, matching_set, topk=topk)
    torchaudio.save(str(output_path), audio[None].cpu(), SAMPLE_RATE)

    duration = audio.shape[-1] / SAMPLE_RATE
    print(f"  Tayyor: {output_path} ({duration:.1f}s)")
    print(f"  Sarflangan vaqt: {format_duration(time.monotonic() - started)}")
    return output_path


if __name__ == "__main__":
    try:
        convert_voice()
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(130)
