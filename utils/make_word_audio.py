#!/usr/bin/env python3
"""
navoiy-tts/inference.py uchun wrapper.

--word qiymati --text ichidagi {word} o'rniga qo'yiladi.

Misol:
    python run_tts.py --word "profil"
    python run_tts.py --word "profil" "sozlamalar" "to'lov"
    python run_tts.py --word "profil" --emotion happy --output audio/profil.wav
"""

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

DEFAULT_TEXT = "Endi {word} sahifasiga kiring."


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="navoiy-tts inference.py ni {word} almashtirish bilan ishga tushiradi.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--word", nargs="+", required=True,
                   help="{word} o'rniga tushadigan so'z(lar). Bir nechta bo'lsa, ketma-ket ishlatiladi.")
    p.add_argument("--text", default=DEFAULT_TEXT,
                   help="Matn shabloni. Ichida {word} bo'lishi kerak.")
    p.add_argument("--script", type=Path, default=Path("navoiy-tts/inference.py"))
    p.add_argument("--cosyvoice-dir", type=Path, default=Path("CosyVoice"))
    p.add_argument("--base-model-dir", type=Path,
                   default=Path("CosyVoice/pretrained_models/CosyVoice2-0.5B"))
    p.add_argument("--checkpoint", type=Path,
                   default=Path("navoiy-tts/emotion_600h_joint.pt"))
    p.add_argument("--reference", type=Path, default=Path("navoiy-tts/demo/xurmo.wav"))
    p.add_argument("--emotion", default="calm")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=1986)
    p.add_argument("--output", type=Path, default=Path("output.wav"),
                   help="Chiqish fayli. Bir nechta so'z berilsa, nomga so'z qo'shiladi.")
    p.add_argument("--dry-run", action="store_true",
                   help="Faqat komandani chop etadi, ishga tushirmaydi.")
    return p.parse_args(argv)


def output_path_for(base: Path, word: str, many: bool) -> Path:
    """Bir nechta so'z uchun output_<word>.wav ko'rinishida nom yasaydi."""
    if not many:
        return base
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in word)
    return base.with_name(f"{base.stem}_{safe}{base.suffix or '.wav'}")


def build_command(args, word: str, output: Path) -> list:
    return [
        sys.executable, str(args.script),
        "--cosyvoice-dir", str(args.cosyvoice_dir),
        "--base-model-dir", str(args.base_model_dir),
        "--checkpoint", str(args.checkpoint),
        "--reference", str(args.reference),
        "--text", args.text.replace("{word}", word),
        "--emotion", args.emotion,
        "--speed", str(args.speed),
        "--seed", str(args.seed),
        "--output", str(output),
    ]


def main():
    args = parse_args()

    if "{word}" not in args.text:
        print("Ogohlantirish: --text ichida {word} yo'q, so'z almashtirilmaydi.", file=sys.stderr)

    if not args.dry_run and not args.script.exists():
        sys.exit(f"Xato: skript topilmadi: {args.script}")

    many = len(args.word) > 1
    failed = []

    for word in args.word:
        out = output_path_for(args.output, word, many)
        if out.parent and str(out.parent) not in ("", "."):
            out.parent.mkdir(parents=True, exist_ok=True)

        cmd = build_command(args, word, out)
        print(">", " ".join(shlex.quote(c) for c in cmd), flush=True)

        if args.dry_run:
            continue

        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"Xato: '{word}' uchun kod {result.returncode} qaytdi.", file=sys.stderr)
            failed.append(word)
        else:
            print(f"Tayyor: {out}", flush=True)

    if failed:
        sys.exit(f"Bajarilmadi: {', '.join(failed)}")


if __name__ == "__main__":
    main()