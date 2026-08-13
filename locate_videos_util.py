#!/usr/bin/env python3
"""
Videolarni manba papkadan destination papkaga tashkillashtirib joylashtiradi.

Manba papkadagi har bir video quyidagicha nomlangan bo'ladi:
    <N> <video nomi>.mp4    masalan: "7 mening videom.mp4"

Har bir video uchun destination papkada quyidagicha struktura yaratiladi:
    <destination>/<name><N>/<name><N>.mp4   -> video faylning o'zi (nusxa)
    <destination>/<name><N>/README.md       -> ichida video nomi

Agar video fayl yoki README.md allaqachon mavjud bo'lsa, ular
qayta yozilmaydi (skip qilinadi).
"""

import os
import re
import shutil

# Fayl nomining boshidagi raqamni ajratib olish uchun regex:
# "7 video nomi.mp4" -> raqam=7, qolgan nomi="video nomi"
FILENAME_PATTERN = re.compile(r"^(\d+)\s+(.+)\.mp4$", re.IGNORECASE)


def organize_videos(source_path: str, destination_path: str, name: str) -> None:
    source_path = os.path.abspath(source_path)
    destination_path = os.path.abspath(destination_path)

    if not os.path.isdir(source_path):
        raise NotADirectoryError(f"Manba papka topilmadi: {source_path}")

    os.makedirs(destination_path, exist_ok=True)

    for filename in sorted(os.listdir(source_path)):
        source_file = os.path.join(source_path, filename)

        if not os.path.isfile(source_file):
            continue

        match = FILENAME_PATTERN.match(filename)
        if not match:
            print(f"[SKIP] Format mos kelmadi: {filename}")
            continue

        number = match.group(1)
        video_title = match.group(2)  # "video nomi" qismi (raqamsiz, kengaytmasiz)

        folder_name = f"{name}{number}"
        target_folder = os.path.join(destination_path, folder_name)
        os.makedirs(target_folder, exist_ok=True)

        target_video = os.path.join(target_folder, f"{folder_name}.mp4")
        target_readme = os.path.join(target_folder, "README.md")

        # Video faylni nusxalash (agar mavjud bo'lmasa)
        if os.path.exists(target_video):
            print(f"[SKIP] Video allaqachon mavjud: {target_video}")
        else:
            shutil.copy2(source_file, target_video)
            print(f"[OK]   Video ko'chirildi: {target_video}")

        # README.md yaratish (agar mavjud bo'lmasa)
        if os.path.exists(target_readme):
            print(f"[SKIP] README.md allaqachon mavjud: {target_readme}")
        else:
            with open(target_readme, "w", encoding="utf-8") as f:
                f.write(video_title + "\n")
            print(f"[OK]   README.md yaratildi: {target_readme}")


def main():
    source_path = input("Videolar joylashgan absolute path: ").strip()
    destination_path = input("Destination path: ").strip()
    name = input("Name: ").strip()

    organize_videos(source_path, destination_path, name)


if __name__ == "__main__":
    main()
