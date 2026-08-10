"""4-bosqich: tarjima qilingan .srt dagi har bir matnni audioga o'girish.

TODO: lokal TTS model orqali amalga oshiriladi.

Reja:
    srt_utils.parse_srt(translated_srt_path) -> Cue ro'yxati olinadi.
    Har bir cue uchun alohida audio fayl generatsiya qilinadi va
    `audios_dir / f"{cue.slug}.wav"` ko'rinishida saqlanadi.

    Fayl nomi MUHIM: u timestamp dagi boshlanish vaqti bo'ladi (00-01-02-500.wav),
    chunki 5-bosqich audioni videoga aynan fayl nomidagi vaqt bo'yicha biriktiradi.
    Bu formatni srt_utils.ms_to_slug() beradi.

    E'tiborga olinadigan nuqtalar:
      - Fayl allaqachon mavjud bo'lsa, uni qayta generatsiya qilmaslik kerak
        (uzilib qolgan jarayonni davom ettirish uchun).
      - Ko'p TTS modellarida matn uzunligiga chegara bor: uzun matnni gaplarga bo'lib,
        keyin ffmpeg concat orqali bitta faylga ulash kerak.
      - Generatsiya qilingan audio cue davomiyligidan uzun chiqsa, keyingi audio bilan
        ustma-ust tushadi. Buni oldini olish uchun TTS tezligini oshirish yoki
        audioni atempo filtri bilan siqish mumkin.

    Variant A — lokal model (masalan Coqui TTS):
        pip install TTS
        from TTS.api import TTS
        tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
        tts.tts_to_file(text=cue.text, language="uz", file_path=str(target))

    Variant B — aisha-ai bulutli xizmati (sinovdan o'tgan):
        pip install aisha-ai
        from aisha_ai import AishaClient
        client = AishaClient(api_key=os.environ["AISHA_API_KEY"], language="uz")
        client.tts(
            transcript=cue.text,
            language="uz",
            model="Gulnoza",      # ovoz modeli
            mood="Neutral",       # Neutral / Cheerful / Happy / Sad
            speed=1.0,            # 0.5 .. 2.0
            output_path=str(target),
        )
        # Chegara: bitta so'rovda 1000 belgigacha matn.

Hozircha bu bosqich QO'LDA bajariladi: foydalanuvchi audiolarni o'zi tayyorlab,
tasdiqlaydi va dastur papkadagi fayllarni tekshiradi.
"""

from __future__ import annotations

from pathlib import Path

from srt_utils import parse_srt
from utils import ask_path, confirm, fail

AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac")


def generate_audios(
    translated_srt_path: str | Path | None = None,
    audios_dir: str | Path | None = None,
) -> Path:
    """Tarjima qilingan .srt dagi har bir matn uchun alohida audio fayl yaratish.

    Args:
        translated_srt_path: Tarjima qilingan .srt fayl manzili. Berilmasa,
            input orqali so'raladi.
        audios_dir: Audiolar saqlanadigan papka manzili. Berilmasa, input orqali
            so'raladi (default qiymat: .srt fayl yonidagi `audios` papkasi).

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
    print(f"  {len(cues)} ta subtitr o'qildi.")

    # --- TODO: shu yerga lokal TTS model orqali generatsiya kodi yoziladi ---

    print(f"  Kutilayotgan fayllar: {audios_dir}/<boshlanish-vaqti>.wav")
    print(f"  Masalan: {audios_dir.name}/{cues[0].slug}.wav")
    confirm("  TTS hozircha qo'lda bajariladi. Audio fayllar tayyormi?")

    missing = [cue for cue in cues if not _find_audio(audios_dir, cue.slug)]
    if missing:
        print(f"  [ogohlantirish] {len(missing)} ta cue uchun audio topilmadi, masalan:")
        for cue in missing[:5]:
            print(f"      {cue.slug}.wav  <-  {cue.text[:50]}")
    if len(missing) == len(cues):
        fail(f"{audios_dir} ichida mos audio fayllar umuman topilmadi.")

    return audios_dir


def _find_audio(audios_dir: Path, slug: str) -> Path | None:
    """Berilgan timestamp uchun audio faylni (kengaytmasidan qat'i nazar) topish."""
    for extension in AUDIO_EXTENSIONS:
        candidate = audios_dir / f"{slug}{extension}"
        if candidate.is_file():
            return candidate
    return None


if __name__ == "__main__":
    result = generate_audios()
    print(f"Tayyor: {result}")
