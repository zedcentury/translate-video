"""5-bosqich: tarjima qilingan .srt dagi har bir matnni audioga o'girish.

Navoiy TTS (CosyVoice2 runtime) orqali amalga oshiriladi. Ya'ni quyidagi
buyruqning dasturiy ko'rinishi:

    python navoiy-tts/inference.py \\
      --cosyvoice-dir CosyVoice \\
      --base-model-dir CosyVoice/pretrained_models/CosyVoice2-0.5B \\
      --checkpoint navoiy-tts/emotion_600h_joint.pt \\
      --reference navoiy-tts/demo/xurmo.wav \\
      --text "..." --emotion calm --output audio.wav

Farqi: model FAQAT BIR MARTA yuklanadi va barcha segmentlar shu bitta
jarayonda generatsiya qilinadi (har bir segment uchun alohida jarayon
ochilsa, 0.5B model qayta-qayta yuklanib, vaqt bir necha barobar oshib ketardi).

Fayl nomi timestamp dagi boshlanish vaqti bo'yicha beriladi (00-01-02-500.wav),
chunki 8-bosqich audioni videoga aynan fayl nomidagi vaqt bo'yicha biriktiradi.

Environment o'zgaruvchilari:
    NAVOIY_REFERENCE   — ovoz namunasi (default: navoiy-tts/demo/xurmo.wav)
    NAVOIY_EMOTION     — hissiyot (default: calm). Ro'yxat: inference.py --list-emotions
    NAVOIY_SPEED       — nutq tezligi (default: 1.0)
    NAVOIY_SEED        — tasodifiylik urug'i (default: 1986)
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

from srt_utils import parse_srt
from utils import ask_path, fail

ROOT = Path(__file__).resolve().parent

COSYVOICE_DIR = Path(os.environ.get("COSYVOICE_DIR", ROOT / "CosyVoice"))
BASE_MODEL_DIR = Path(
    os.environ.get("COSYVOICE_MODEL_DIR", COSYVOICE_DIR / "pretrained_models" / "CosyVoice2-0.5B")
)
NAVOIY_DIR = Path(os.environ.get("NAVOIY_DIR", ROOT / "navoiy-tts"))
CHECKPOINT = Path(os.environ.get("NAVOIY_CHECKPOINT", NAVOIY_DIR / "emotion_600h_joint.pt"))
REFERENCE = Path(os.environ.get("NAVOIY_REFERENCE", NAVOIY_DIR / "demo" / "xurmo.wav"))
EMOTIONS_FILE = Path(os.environ.get("NAVOIY_EMOTIONS_FILE", NAVOIY_DIR / "emotions_40h.json"))

DEFAULT_EMOTION = os.environ.get("NAVOIY_EMOTION", "calm")
DEFAULT_SPEED = float(os.environ.get("NAVOIY_SPEED", "1.0"))
DEFAULT_SEED = int(os.environ.get("NAVOIY_SEED", "1986"))

SAMPLE_RATE = 24000
AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac")

# Matnni normalize qilish 4-bosqichga ko'chirildi (step4_normalize_srt.py), shuning
# uchun bu yerda takroran normalize qilinmaydi — aks holda 4-bosqichda almashtirilgan
# atamalar yana o'zgarib ketishi mumkin. Agar bu bosqichga normalize qilinmagan .srt
# berilsa, True qilib qo'yish kerak.
NORMALIZE_TEXT = False
NORMALIZE_MODE = "infer"

# Generatsiya qilingan audio o'z segmentiga sig'masa (keyingi segment boshlanishidan
# oshib ketsa), ffmpeg `atempo` orqali tezlashtiriladi. Tovush balandligi (pitch)
# o'zgarmaydi. False qilinsa, audiolar ustma-ust tushishi mumkin.
FIT_TO_TIMELINE = True
MAX_TEMPO = 1.5  # bundan ortiq tezlashtirish nutqni tushunarsiz qiladi
TEMPO_TOLERANCE_MS = 150  # shu qadar oshib ketishga e'tibor berilmaydi


def generate_audios(
    translated_srt_path: str | Path | None = None,
    audios_dir: str | Path | None = None,
    reference: str | Path = REFERENCE,
    emotion: str = DEFAULT_EMOTION,
    speed: float = DEFAULT_SPEED,
) -> Path:
    """Tarjima qilingan .srt dagi har bir matn uchun alohida audio fayl yaratish.

    Args:
        translated_srt_path: Tarjima qilingan .srt fayl manzili. Berilmasa,
            input orqali so'raladi.
        audios_dir: Audiolar saqlanadigan papka manzili. Berilmasa, input orqali
            so'raladi (default qiymat: .srt fayl yonidagi `audios` papkasi).
        reference: Ovoz namunasi (.wav) — qaysi ovozda gapirilishi shundan olinadi.
        emotion: Hissiyot nomi yoki tegi (masalan: calm, happy, sad).
        speed: Nutq tezligi (1.0 — normal).

    Returns:
        Audiolar saqlangan papka manzili.
    """
    if translated_srt_path is None:
        translated_srt_path = ask_path(
            "Tarjima qilingan .srt fayl manzilini kiriting", must_exist=True
        )
    translated_srt_path = Path(translated_srt_path).expanduser().resolve()

    if audios_dir is None:
        audios_dir = ask_path(
            "Audiolar qaysi papkaga saqlansin",
            default=translated_srt_path.parent / "audios",
        )
    audios_dir = Path(audios_dir).expanduser().resolve()
    audios_dir.mkdir(parents=True, exist_ok=True)

    cues = parse_srt(translated_srt_path)
    if not cues:
        fail(f"{translated_srt_path} ichida subtitr topilmadi.")

    # Har bir segment uchun ajratilgan vaqt: keyingi segment boshlanishigacha (ms).
    gaps = [
        cues[position + 1].start_ms - cue.start_ms if position + 1 < len(cues) else None
        for position, cue in enumerate(cues)
    ]

    pending = [
        (cue, gap) for cue, gap in zip(cues, gaps) if _find_audio(audios_dir, cue.slug) is None
    ]
    print(f"  {len(cues)} ta subtitr | {len(cues) - len(pending)} tasi allaqachon tayyor")
    if not pending:
        print("  Barcha audiolar mavjud, TTS o'tkazib yuborildi.")
        return audios_dir

    tts = NavoiyTTS(reference=reference, emotion=emotion, speed=speed)

    started = time.monotonic()
    for position, (cue, gap_ms) in enumerate(pending, start=1):
        target = audios_dir / f"{cue.slug}.wav"
        print(f"  [{position}/{len(pending)}] {cue.slug} : {cue.text[:60]}")

        duration = tts.synthesize(cue.text, target)
        if FIT_TO_TIMELINE:
            duration = fit_to_gap(target, duration, gap_ms)

        elapsed = time.monotonic() - started
        remaining = (elapsed / position) * (len(pending) - position)
        print(f"      {duration:.1f}s audio | taxminan {remaining / 60:.1f} daqiqa qoldi")

    return audios_dir


class NavoiyTTS:
    """CosyVoice2 + Navoiy checkpoint — model bir marta yuklanadi."""

    def __init__(
        self,
        reference: str | Path = REFERENCE,
        emotion: str = DEFAULT_EMOTION,
        speed: float = DEFAULT_SPEED,
        seed: int = DEFAULT_SEED,
    ) -> None:
        self.reference = Path(reference).expanduser().resolve()
        self.speed = speed
        self.seed = seed

        for path, label in (
            (COSYVOICE_DIR, "CosyVoice papkasi"),
            (BASE_MODEL_DIR, "asosiy model"),
            (CHECKPOINT, "checkpoint"),
            (self.reference, "ovoz namunasi (.wav)"),
            (EMOTIONS_FILE, "hissiyotlar fayli"),
        ):
            if not path.exists():
                fail(f"{label} topilmadi: {path}")

        helpers = _load_inference_helpers()
        _entries, lookup = helpers.load_emotions(EMOTIONS_FILE)
        entry = lookup.get(emotion.lower().strip("[]"))
        if entry is None:
            fail(f"Noma'lum hissiyot: {emotion!r}. Mavjudlari: {', '.join(sorted(lookup))}")
        self.instruction = entry["instruct"].strip() + "<|endofprompt|>"

        # CosyVoice va uztts modullari sys.path ga qo'shiladi (inference.py dagidek).
        for path in (COSYVOICE_DIR, COSYVOICE_DIR / "third_party" / "Matcha-TTS", NAVOIY_DIR):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))

        import torch
        import torchaudio
        from cosyvoice.cli.cosyvoice import CosyVoice2
        from uztts.normalize import normalize

        self.torch = torch
        self.torchaudio = torchaudio
        self.normalize = normalize

        self.has_cuda = torch.cuda.is_available()
        if not self.has_cuda:
            print("  CUDA topilmadi — CPU da ishlaydi (sekinroq).")

        print(f"  Model yuklanmoqda: {BASE_MODEL_DIR.name} | hissiyot: {emotion}")
        self.model = CosyVoice2(
            str(BASE_MODEL_DIR.resolve()), load_jit=False, load_trt=False, fp16=self.has_cuda
        )
        state = helpers.unwrap_state_dict(
            torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
        )
        incompatible = self.model.model.llm.load_state_dict(state, strict=False)
        if incompatible.missing_keys:
            print(f"  [ogohlantirish] {len(incompatible.missing_keys)} ta kalit yetishmadi")
        if incompatible.unexpected_keys:
            print(f"  [ogohlantirish] {len(incompatible.unexpected_keys)} ta ortiqcha kalit")
        self.model.model.llm.eval()

    def synthesize(self, text: str, output_path: Path) -> float:
        """Matnni audioga o'girib, `output_path` ga saqlash. Davomiyligini qaytaradi."""
        # Har bir segment uchun bir xil urug' — ovoz segmentdan segmentga o'zgarmaydi.
        import random

        random.seed(self.seed)
        self.torch.manual_seed(self.seed)
        if self.has_cuda:
            self.torch.cuda.manual_seed_all(self.seed)

        chunks = []
        with self.torch.inference_mode():
            for result in self.model.inference_instruct2(
                self.normalize(text, mode=NORMALIZE_MODE) if NORMALIZE_TEXT else text,
                self.instruction,
                str(self.reference),
                stream=False,
                speed=self.speed,
            ):
                chunks.append(result["tts_speech"].detach().cpu())
        if not chunks:
            fail(f"Model audio qaytarmadi: {text[:60]!r}")

        audio = self.torch.cat(chunks, dim=1)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.torchaudio.save(str(output_path), audio, SAMPLE_RATE)
        return audio.shape[-1] / SAMPLE_RATE


def fit_to_gap(audio_path: Path, duration: float, gap_ms: int | None) -> float:
    """Audio o'z oralig'iga sig'masa, ffmpeg `atempo` bilan tezlashtirish."""
    if gap_ms is None:
        return duration  # oxirgi segment — chegara yo'q

    overflow_ms = duration * 1000 - gap_ms
    if overflow_ms <= TEMPO_TOLERANCE_MS:
        return duration

    tempo = min((duration * 1000) / gap_ms, MAX_TEMPO)
    fitted = audio_path.with_name(f"{audio_path.stem}__fitted{audio_path.suffix}")
    process = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(audio_path),
            "-filter:a", f"atempo={tempo:.4f}",
            str(fitted),
        ],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        print(f"      [ogohlantirish] tezlashtirib bo'lmadi: {process.stderr.strip()}")
        fitted.unlink(missing_ok=True)
        return duration

    fitted.replace(audio_path)
    new_duration = duration / tempo
    print(f"      {overflow_ms / 1000:.1f}s oshib ketdi -> {tempo:.2f}x tezlashtirildi")
    return new_duration


def _load_inference_helpers():
    """navoiy-tts/inference.py ni modul sifatida yuklash.

    Papka nomida `-` bo'lgani uchun oddiy `import` ishlamaydi, shuning uchun
    fayl manzili orqali yuklaymiz — emotion va checkpoint mantig'i takrorlanmasin.
    """
    path = NAVOIY_DIR / "inference.py"
    if not path.is_file():
        fail(f"inference.py topilmadi: {path}")
    spec = importlib.util.spec_from_file_location("navoiy_inference", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_audio(audios_dir: Path, slug: str) -> Path | None:
    """Berilgan timestamp uchun audio faylni (kengaytmasidan qat'i nazar) topish."""
    for extension in AUDIO_EXTENSIONS:
        candidate = audios_dir / f"{slug}{extension}"
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


if __name__ == "__main__":
    result = generate_audios()
    print(f"Tayyor: {result}")
