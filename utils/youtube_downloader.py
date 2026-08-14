#!/usr/bin/env python3
"""
YouTube video yuklovchi.

Ishlash tartibi:
  1. Foydalanuvchidan YouTube video linki so'raladi.
  2. Video uchun mavjud sifatlar (quality) ro'yxati chiqariladi.
  3. Foydalanuvchi raqam orqali sifatni tanlaydi.
  4. Video "assets" papkasiga yuklab olinadi.

Talablar:
  pip install yt-dlp
  ffmpeg  (video va audio oqimlarini birlashtirish uchun)
"""

import os
import shutil
import sys

try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError
except ImportError:
    sys.exit("Xatolik: yt-dlp o'rnatilmagan.\nO'rnatish uchun: pip install yt-dlp")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")


# ---------------------------------------------------------------- yordamchilar

def human_size(num_bytes):
    """Baytni o'qishga qulay ko'rinishga o'tkazadi."""
    if not num_bytes:
        return "noma'lum"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024


def human_duration(seconds):
    """Sekundni soat:daqiqa:sekund ko'rinishiga o'tkazadi."""
    if not seconds:
        return "noma'lum"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def has_ffmpeg():
    return shutil.which("ffmpeg") is not None


# ------------------------------------------------------------ ma'lumot olish

def fetch_info(url):
    """Video haqidagi metama'lumotni yuklamasdan oladi."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def collect_qualities(info):
    """Mavjud formatlardan takrorlanmas sifatlar ro'yxatini yig'adi."""
    best_by_height = {}

    for fmt in info.get("formats", []):
        if fmt.get("vcodec") in (None, "none"):  # faqat audio - o'tkazib yuboramiz
            continue
        height = fmt.get("height")
        if not height:
            continue

        size = fmt.get("filesize") or fmt.get("filesize_approx") or 0
        candidate = {
            "height": height,
            "fps": fmt.get("fps"),
            "ext": fmt.get("ext"),
            "size": size,
            "note": fmt.get("format_note") or "",
        }

        current = best_by_height.get(height)
        # Har bir sifat uchun mp4 ni afzal ko'ramiz, aks holda hajmi kattaroqni
        if current is None:
            best_by_height[height] = candidate
        else:
            better_ext = candidate["ext"] == "mp4" and current["ext"] != "mp4"
            bigger = candidate["size"] > current["size"] and current["ext"] == candidate["ext"]
            if better_ext or bigger:
                best_by_height[height] = candidate

    qualities = sorted(best_by_height.values(), key=lambda q: q["height"], reverse=True)
    return qualities


# ------------------------------------------------------------------- interfeys

def ask_url():
    """1-input: video linkini so'raydi."""
    while True:
        url = input("YouTube video linkini kiriting: ").strip()
        if not url:
            print("  Link bo'sh bo'lishi mumkin emas. Qaytadan urinib ko'ring.\n")
            continue
        if "youtube.com" not in url and "youtu.be" not in url:
            print("  Bu YouTube linkiga o'xshamayapti. Qaytadan urinib ko'ring.\n")
            continue
        return url


def ask_quality(qualities, merge_ok):
    """2-input: sifatni tanlash menyusini ko'rsatadi."""
    print("\nMavjud sifatlar:")
    print("-" * 52)

    for i, q in enumerate(qualities, start=1):
        fps = f" {int(q['fps'])}fps" if q.get("fps") else ""
        size = human_size(q["size"])
        print(f"  [{i}]  {q['height']}p{fps:<7}  {q['ext']:<5}  ~{size}")

    audio_index = len(qualities) + 1
    print(f"  [{audio_index}]  Faqat audio (mp3)")
    print("-" * 52)

    if not merge_ok:
        print("Diqqat: ffmpeg topilmadi — yuqori sifatlar audiosiz bo'lishi mumkin.")

    while True:
        choice = input(f"Sifatni tanlang (1-{audio_index}): ").strip()
        if not choice.isdigit():
            print("  Iltimos, raqam kiriting.")
            continue
        num = int(choice)
        if num == audio_index:
            return None  # audio rejimi
        if 1 <= num <= len(qualities):
            return qualities[num - 1]
        print(f"  1 dan {audio_index} gacha bo'lgan raqamni kiriting.")


# -------------------------------------------------------------------- yuklash

def progress_hook(d):
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "").strip()
        speed = d.get("_speed_str", "").strip()
        eta = d.get("_eta_str", "").strip()
        print(f"\r  Yuklanmoqda: {percent}  |  {speed}  |  qoldi: {eta}   ", end="")
    elif d["status"] == "finished":
        print("\r  Yuklab olindi, fayl tayyorlanmoqda...          ")


def download(url, quality, merge_ok):
    os.makedirs(ASSETS_DIR, exist_ok=True)

    opts = {
        "outtmpl": os.path.join(ASSETS_DIR, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,  # fayl nomidagi maxsus belgilarni tozalaydi
    }

    if quality is None:
        # Faqat audio
        opts["format"] = "bestaudio/best"
        if merge_ok:
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
    else:
        height = quality["height"]
        if merge_ok:
            # Eng yaxshi video + eng yaxshi audio, keyin birlashtiriladi
            opts["format"] = (
                f"bestvideo[height<={height}]+bestaudio/"
                f"best[height<={height}]"
            )
            opts["merge_output_format"] = "mp4"
        else:
            # ffmpeg yo'q — audio bilan birga kelgan yagona faylni olamiz
            opts["format"] = f"best[height<={height}]"

    with YoutubeDL(opts) as ydl:
        ydl.download([url])


# ----------------------------------------------------------------------- main

def main():
    print("=" * 52)
    print("  YouTube video yuklovchi")
    print("=" * 52 + "\n")

    url = ask_url()

    print("\nVideo ma'lumotlari olinmoqda...")
    try:
        info = fetch_info(url)
    except DownloadError:
        sys.exit("Xatolik: video topilmadi yoki link noto'g'ri.")
    except Exception as e:
        sys.exit(f"Xatolik: {e}")

    title = info.get("title") or "noma'lum"
    uploader = info.get("uploader") or "noma'lum"

    print(f"\nSarlavha : {title}")
    print(f"Kanal    : {uploader}")
    print(f"Davomiyl.: {human_duration(info.get('duration'))}")

    qualities = collect_qualities(info)
    if not qualities:
        sys.exit("Xatolik: bu video uchun sifat variantlari topilmadi.")

    merge_ok = has_ffmpeg()
    quality = ask_quality(qualities, merge_ok)

    label = "audio (mp3)" if quality is None else f"{quality['height']}p"
    print(f"\n'{label}' sifatida yuklab olinmoqda...\n")

    try:
        download(url, quality, merge_ok)
    except DownloadError as e:
        sys.exit(f"\nYuklashda xatolik: {e}")
    except KeyboardInterrupt:
        sys.exit("\n\nBekor qilindi.")

    print(f"\nTayyor! Fayl saqlandi: {ASSETS_DIR}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBekor qilindi.")
