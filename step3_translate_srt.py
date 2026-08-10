"""3-bosqich: .srt fayldagi matnlarni bir tildan boshqa tilga tarjima qilish.

TODO: claude / chatgpt / gemini API'lari orqali amalga oshiriladi.

Reja:
    srt_utils.parse_srt(srt_path) -> Cue ro'yxati olinadi.
    Cue'lar bloklarga (masalan 20-50 tadan) bo'linib LLM ga yuboriladi —
    bir vaqtning o'zida bir nechta gap berilsa, kontekst saqlanadi va tarjima sifati oshadi.

    Muhim nuqtalar:
      - Cue raqamlari va vaqtlari O'ZGARMAYDI, faqat matn tarjima qilinadi.
      - Javob formatini qat'iy belgilash kerak (masalan JSON: {"1": "...", "2": "..."}),
        aks holda qaysi tarjima qaysi cue'ga tegishli ekanini aniqlash qiyin bo'ladi.
      - Kiruvchi va chiquvchi cue'lar soni bir xilligini tekshirish kerak.
      - Oldingi/keyingi bir nechta cue kontekst sifatida berilsa, olmoshlar to'g'ri tarjima bo'ladi.

    Masalan (Anthropic SDK):
        pip install anthropic

        from anthropic import Anthropic
        client = Anthropic()   # ANTHROPIC_API_KEY environment o'zgaruvchisidan oladi
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=8000,
            system=f"Translate subtitles from {src_language} to {dst_language}. ...",
            messages=[{"role": "user", "content": batch_as_json}],
        )

    So'ngra tarjima qilingan matnlar bilan yangi Cue'lar yasab,
    srt_utils.write_srt(cues, translated_srt_path) chaqiriladi.

Hozircha bu bosqich QO'LDA bajariladi: foydalanuvchi tarjimani o'zi tayyorlab,
tasdiqlaydi va dastur faylning mavjudligini tekshiradi.
"""

from __future__ import annotations

from pathlib import Path

from utils import ask_path, confirm, fail

DEFAULT_SRC_LANGUAGE = "en"
DEFAULT_DST_LANGUAGE = "uz"


def translate_srt(
    srt_path: str | Path | None = None,
    translated_srt_path: str | Path | None = None,
    src_language: str = DEFAULT_SRC_LANGUAGE,
    dst_language: str = DEFAULT_DST_LANGUAGE,
) -> Path:
    """.srt fayldagi matnlarni tarjima qilib, yangi .srt fayl yaratish.

    Args:
        srt_path: Manba .srt fayl manzili. Berilmasa, input orqali so'raladi.
        translated_srt_path: Natijaviy .srt fayl manzili. Berilmasa, input orqali
            so'raladi (default qiymat: `<nom>-<dst_language>.srt`).
        src_language: Manba til (default: "en").
        dst_language: Tarjima tili (default: "uz").

    Returns:
        Tarjima qilingan .srt faylning manzili.
    """
    if srt_path is None:
        srt_path = ask_path("Tarjima qilinadigan .srt fayl manzilini kiriting", must_exist=True)
    srt_path = Path(srt_path).expanduser().resolve()

    if translated_srt_path is None:
        translated_srt_path = ask_path(
            "Tarjima qilingan .srt fayl qayerga saqlansin",
            default=srt_path.with_name(f"{srt_path.stem}-{dst_language}.srt"),
        )
    translated_srt_path = Path(translated_srt_path).expanduser().resolve()

    # --- TODO: shu yerga LLM orqali tarjima kodi yoziladi ---

    print(f"  Yo'nalish: {src_language} -> {dst_language}")
    print(f"  Kutilayotgan fayl: {translated_srt_path}")
    confirm(f"  Tarjima hozircha qo'lda bajariladi. {translated_srt_path.name} tayyormi?")
    if not translated_srt_path.is_file():
        fail(f"{translated_srt_path} topilmadi.")
    return translated_srt_path


if __name__ == "__main__":
    result = translate_srt()
    print(f"Tayyor: {result}")
