#!/usr/bin/env python3
"""
YouTube video yuklovchi.

Ishlash tartibi:
  1. Foydalanuvchidan YouTube video linki so'raladi.
  2. Video uchun mavjud sifatlar (quality) ro'yxati chiqariladi.
  3. Foydalanuvchi raqam orqali sifatni tanlaydi.
  4. Video "assets" papkasiga yuklab olinadi.

YouTube ba'zan "Sign in to confirm you're not a bot" deb javob beradi. Bunday
holatda brauzeringizdagi cookie'lar kerak bo'ladi — dastur qaysi brauzerdan
olishni so'raydi (YouTube'ga kirgan brauzerni tanlang). Savol berilmasligi uchun
oldindan ham ko'rsatib qo'yish mumkin:

  YT_COOKIES_BROWSER=chrome python utils/youtube_downloader.py
  YT_COOKIES_FILE=/path/to/cookies.txt python utils/youtube_downloader.py

Metama'lumot olinsa ham, media oqimi "HTTP Error 403: Forbidden" berishi mumkin.
Sabab — YouTube format havolalarini o'zi bergan "player client" ga bog'laydi.
Bunda dastur boshqa client'lar bilan avtomatik qayta urinadi (android, tv,
web_safari, ios, mweb). Aniq bittasini majburlash uchun:

  YT_PLAYER_CLIENT=android python utils/youtube_downloader.py

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

# Cookie olish mumkin bo'lgan brauzerlar: (yt-dlp nomi, ko'rinadigan nom, tekshiriladigan papka).
BROWSERS = [
    ("chrome", "Google Chrome", "~/Library/Application Support/Google/Chrome"),
    ("brave", "Brave", "~/Library/Application Support/BraveSoftware"),
    ("firefox", "Firefox", "~/Library/Application Support/Firefox"),
    ("safari", "Safari", "~/Library/Safari"),
    ("edge", "Microsoft Edge", "~/Library/Application Support/Microsoft Edge"),
    ("chromium", "Chromium", "~/Library/Application Support/Chromium"),
]

# YouTube bot tekshiruvi ishga tushganini shu iboralardan bilamiz.
BOT_CHECK_HINTS = ("sign in to confirm", "not a bot", "cookies", "age-restricted", "login required")

# Metama'lumot olinsa ham, media oqimining o'zi 403 qaytarishi mumkin: YouTube
# format havolalarini o'zi bergan "player client" ga bog'lab qo'yadi va boshqa
# client so'raganda rad etadi. Shunda navbatma-navbat boshqa client'lar
# sinaladi — birortasi albatta ishlaydi (default = yt-dlp o'zi tanlagani).
FALLBACK_CLIENTS = ["android", "tv", "web_safari", "ios", "mweb"]

# Boshqa client bilan qayta urinib ko'rishga arziydigan xatoliklar.
RETRY_HINTS = (
    "403", "forbidden",
    "requested format is not available",
    "unable to download video data",
    "page needs to be reloaded",
    "unable to download webpage",
    "fragment",
)


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


# --------------------------------------------------------------------- cookie

def cookie_opts(source):
    """Tanlangan cookie manbasini yt-dlp tushunadigan sozlamaga aylantiradi.

    `source` — ("browser", "chrome") yoki ("file", "/path/cookies.txt") yoki None.
    """
    if not source:
        return {}
    kind, value = source
    if kind == "file":
        return {"cookiefile": value}
    # yt-dlp tuple kutadi: (brauzer, profil, keyring, konteyner).
    return {"cookiesfrombrowser": (value, None, None, None)}


def cookies_from_env():
    """Environment o'zgaruvchilaridan cookie manbasini olish (savol berilmaydi)."""
    path = os.environ.get("YT_COOKIES_FILE")
    if path:
        if not os.path.isfile(os.path.expanduser(path)):
            sys.exit(f"Xatolik: cookie fayli topilmadi: {path}")
        return ("file", os.path.expanduser(path))

    browser = os.environ.get("YT_COOKIES_BROWSER")
    if browser:
        return ("browser", browser.strip().lower())
    return None


def installed_browsers():
    """Shu kompyuterda o'rnatilgan brauzerlar ro'yxati."""
    found = []
    for name, label, folder in BROWSERS:
        if os.path.isdir(os.path.expanduser(folder)):
            found.append((name, label))
    return found


def looks_like_bot_check(error):
    """Xatolik YouTube'ning autentifikatsiya talabimi?"""
    message = str(error).lower()
    return any(hint in message for hint in BOT_CHECK_HINTS)


def looks_retryable(error):
    """Boshqa player client bilan qayta urinib ko'rishga arziydimi?"""
    message = str(error).lower()
    return any(hint in message for hint in RETRY_HINTS) or looks_like_bot_check(error)


def client_opts(player_client):
    """Tanlangan player client'ni yt-dlp sozlamasiga aylantiradi."""
    if not player_client:
        return {}
    return {"extractor_args": {"youtube": {"player_client": [player_client]}}}


def ask_cookies():
    """Bot tekshiruvi chiqqanda cookie manbasini so'raydi."""
    browsers = installed_browsers()

    print("\n" + "-" * 52)
    print("  YouTube autentifikatsiya so'rayapti (bot tekshiruvi).")
    print("  YouTube'ga kirgan brauzerni tanlang — cookie'lari ishlatiladi.")
    print("-" * 52)

    for i, (_name, label) in enumerate(browsers, start=1):
        print(f"  [{i}]  {label}")
    file_index = len(browsers) + 1
    print(f"  [{file_index}]  cookies.txt faylini ko'rsataman")
    print(f"  [{file_index + 1}]  Bekor qilish")
    print("-" * 52)

    while True:
        choice = input(f"Tanlang (1-{file_index + 1}): ").strip()
        if not choice.isdigit():
            print("  Iltimos, raqam kiriting.")
            continue
        num = int(choice)
        if num == file_index + 1:
            return None
        if num == file_index:
            path = os.path.expanduser(input("cookies.txt manzili: ").strip().strip("'\""))
            if not os.path.isfile(path):
                print(f"  Bunday fayl topilmadi: {path}")
                continue
            return ("file", path)
        if 1 <= num <= len(browsers):
            return ("browser", browsers[num - 1][0])
        print(f"  1 dan {file_index + 1} gacha bo'lgan raqamni kiriting.")


# ------------------------------------------------------------ ma'lumot olish

def fetch_info(url, cookies=None):
    """Video haqidagi metama'lumotni yuklamasdan oladi."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        **cookie_opts(cookies),
    }
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def collect_qualities(info):
    """Mavjud formatlardan takrorlanmas sifatlar ro'yxatini yig'adi."""
    best_by_height = {}

    for fmt in info.get("formats", []):
        if fmt.get("vcodec") in (None, "none"):      # faqat audio - o'tkazib yuboramiz
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
            return None                      # audio rejimi
        if 1 <= num <= len(qualities):
            return qualities[num - 1]
        print(f"  1 dan {audio_index} gacha bo'lgan raqamni kiriting.")


def ask_thumbnail():
    """3-input: thumbnail ham yuklab olinsinmi? Default javob - yo'q."""
    while True:
        answer = input("\nVideo thumbnail'i ham yuklab olinsinmi? (ha/yo'q) [yo'q]: ").strip().lower()

        if answer == "":                                  # Enter bosilsa - default
            return False
        if answer in ("h", "ha", "y", "yes", "ok"):
            return True
        if answer in ("y'", "yo", "yoq", "yo'q", "n", "no"):
            return False

        print("  'ha' yoki 'yo'q' deb javob bering (Enter - yo'q).")


# -------------------------------------------------------------------- yuklash

def progress_hook(d):
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "").strip()
        speed = d.get("_speed_str", "").strip()
        eta = d.get("_eta_str", "").strip()
        print(f"\r  Yuklanmoqda: {percent}  |  {speed}  |  qoldi: {eta}   ", end="")
    elif d["status"] == "finished":
        print("\r  Yuklab olindi, fayl tayyorlanmoqda...          ")


def download(url, quality, merge_ok, want_thumbnail=False, cookies=None, player_client=None):
    os.makedirs(ASSETS_DIR, exist_ok=True)

    opts = {
        "outtmpl": os.path.join(ASSETS_DIR, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,   # fayl nomidagi maxsus belgilarni tozalaydi
        # Ma'lumot olishda ishlagan cookie'lar yuklashda ham kerak bo'ladi.
        **cookie_opts(cookies),
        **client_opts(player_client),
    }

    postprocessors = []

    if want_thumbnail:
        # Thumbnail video bilan bir xil nom ostida alohida rasm fayli sifatida saqlanadi
        opts["writethumbnail"] = True
        if merge_ok:
            # YouTube ko'pincha .webp beradi - ffmpeg bo'lsa .jpg ga o'giramiz
            postprocessors.append({
                "key": "FFmpegThumbnailsConvertor",
                "format": "jpg",
                "when": "before_dl",
            })

    if quality is None:
        # Faqat audio
        opts["format"] = "bestaudio/best"
        if merge_ok:
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            })
    else:
        height = quality["height"]
        # Oxiridagi "/best" — zaxira client'lar uchun. Ular ko'pincha kamroq
        # format beradi va aniq balandlik topilmasa "Requested format is not
        # available" bilan to'xtab qolardi; endi bunday holatda mavjud eng
        # yaxshisi olinadi.
        if merge_ok:
            # Eng yaxshi video + eng yaxshi audio, keyin birlashtiriladi
            opts["format"] = (
                f"bestvideo[height<={height}]+bestaudio/"
                f"best[height<={height}]/best"
            )
            opts["merge_output_format"] = "mp4"
        else:
            # ffmpeg yo'q — audio bilan birga kelgan yagona faylni olamiz
            opts["format"] = f"best[height<={height}]/best"

    if postprocessors:
        opts["postprocessors"] = postprocessors

    with YoutubeDL(opts) as ydl:
        ydl.download([url])


# ----------------------------------------------------------------------- main

def main():
    print("=" * 52)
    print("  YouTube video yuklovchi")
    print("=" * 52 + "\n")

    url = ask_url()
    cookies = cookies_from_env()
    if cookies:
        print(f"\nCookie manbasi: {cookies[1]} (environment orqali)")

    print("\nVideo ma'lumotlari olinmoqda...")
    try:
        info = fetch_info(url, cookies)
    except DownloadError as e:
        # Bot tekshiruvi bo'lsa, cookie so'rab bir marta qayta urinamiz.
        if not looks_like_bot_check(e) or cookies:
            sys.exit(f"Xatolik: {e}")

        cookies = ask_cookies()
        if not cookies:
            sys.exit("Bekor qilindi.")

        print(f"\nCookie olinmoqda ({cookies[1]}) va qayta urinilmoqda...")
        try:
            info = fetch_info(url, cookies)
        except DownloadError as retry_error:
            sys.exit(f"Xatolik: {retry_error}")
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
    want_thumbnail = ask_thumbnail()

    label = "audio (mp3)" if quality is None else f"{quality['height']}p"
    extra = " + thumbnail" if want_thumbnail else ""
    print(f"\n'{label}{extra}' yuklab olinmoqda...\n")

    # Birinchi urinish — yt-dlp o'zi tanlagan client bilan. 403 yoki shunga
    # o'xshash xato chiqsa, zaxira client'lar navbat bilan sinaladi.
    forced = os.environ.get("YT_PLAYER_CLIENT")
    attempts = [forced] if forced else [None] + FALLBACK_CLIENTS

    last_error = None
    done = False
    for attempt, player_client in enumerate(attempts, start=1):
        if attempt > 1:
            print(f"\n  Boshqa usul sinalmoqda: player_client={player_client}\n")
        try:
            download(url, quality, merge_ok, want_thumbnail, cookies, player_client)
            done = True
            break
        except DownloadError as e:
            last_error = e
            # Qayta urinishga arzimaydigan xato bo'lsa, qolganini sinab o'tirmaymiz.
            if not looks_retryable(e):
                break
        except KeyboardInterrupt:
            sys.exit("\n\nBekor qilindi.")

    if not done:
        print(f"\nYuklashda xatolik: {last_error}")
        if looks_retryable(last_error):
            sys.exit(
                "\nHamma usul sinab ko'rildi. Maslahatlar:\n"
                "  - bir necha daqiqa kutib qayta urinib ko'ring "
                "(ketma-ket so'rovlardan keyin YouTube vaqtincha cheklaydi);\n"
                "  - YouTube'ga kirgan brauzer cookie'sidan foydalaning:\n"
                "      YT_COOKIES_BROWSER=chrome python utils/youtube_downloader.py\n"
                "  - aniq bitta usulni majburlang:\n"
                "      YT_PLAYER_CLIENT=android python utils/youtube_downloader.py"
            )
        sys.exit(1)

    print(f"\nTayyor! Fayl saqlandi: {ASSETS_DIR}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBekor qilindi.")