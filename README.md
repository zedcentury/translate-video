# Video tarjimon: ingliz → o'zbek dublyaj

Ingliz tilidagi videoni o'zbek tilida gapiriladigan variantga o'tkazish uchun mo'ljallangan 7 bosqichli quvur
(pipeline). Har bir bosqich alohida faylda va uni **mustaqil ravishda** ham, `modes/` dagi rejimlar orqali
**ketma-ket** ham ishga tushirish mumkin.

## Video turini tanlang

| Qo'llanma | Rejim | Qachon |
|---|---|---|
| **[readme/COURSE.md](readme/COURSE.md)** | `modes/course.py` | kurs, ma'ruza, skrinkast — fon ovozi kerak emas |
| **[readme/MOVIE.md](readme/MOVIE.md)** | `modes/movie.py` | kino, film, serial — fon musiqasi va effektlar muhim |

Ikkala qo'llanma ham to'liq: rejimni ishga tushirishdan tortib har bir bosqichni alohida bajarishgacha.
Quyida esa ikkalasiga umumiy bo'lgan narsalar — o'rnatish, struktura, ko'p video bilan ishlash va sozlamalar.

---

## Bosqichlar

| #  | Fayl                       | Nima qiladi                                                  | Vosita                          |
|----|----------------------------|--------------------------------------------------------------|---------------------------------|
| 1a | `steps/remove_audio.py`    | Videodan audio qismini butunlay olib tashlaydi               | ffmpeg                          |
| 1b | `steps/remove_vocals.py`   | Videodan faqat odam nutqini olib tashlaydi, fonni qoldiradi  | demucs + ffmpeg                 |
| 2  | `steps/extract_audio.py`   | Asl videodan audio ajratib oladi                             | ffmpeg                          |
| 3  | `steps/generate_srt.py`    | Audiodan inglizcha `.srt` yasaydi                            | openai-whisper `large-v3-turbo` |
| 4  | `steps/translate_srt.py`   | `.srt` ni o'zbekchaga tarjima qiladi                         | Claude Code headless (opus 5)   |
| 5  | `steps/normalize_srt.py`   | Sonlar/sanalarni so'zga aylantiradi, atamalarni almashtiradi | uztts                           |
| 6  | `steps/generate_audios.py` | Har bir subtitr uchun audio generatsiya qiladi               | Navoiy TTS (CosyVoice2)         |
| 7  | `steps/merge_audios.py`    | O'zbekcha audiolarni timestamp bo'yicha qo'yadi              | ffmpeg                          |

1-bosqich **rejimga qarab** tanlanadi: `course.py` → `1a`, `movie.py` → `1b`. Qolgan bosqichlar ikkalasida ham
bir xil.

> **Diqqat:** 2-bosqich transkripsiya uchun **asl** videodan audio oladi (nutq faqat o'sha yerda),
> 7-bosqich esa 1-bosqichda tayyorlangan videoni ishlatadi.

## Loyiha strukturasi

```
readme/       ← video turiga qarab qo'llanmalar
│             COURSE.md — kurs videolari uchun
│             MOVIE.md  — kinolar uchun
steps/        ← quvurning alohida bosqichlari (har birini mustaqil ishga tushirsa bo'ladi)
modes/        ← tayyor rejimlar: butun quvurni ma'lum bir video turi uchun bajaradi
│             course.py — kurs videolari uchun (fon ovozi tashlab yuboriladi)
│             movie.py  — kinolar uchun (fon musiqasi va effektlar saqlanadi)
pipelines/    ← bir nechta bosqichni ketma-ket bajaradigan qisqartirilgan quvurlar
│             prepare.py — tarjimadan oldingi tayyorgarlik (1-3 bosqichlar)
batches/      ← bir nechta video uchun quvurlarni ketma-ket ishga tushiruvchi kodlar
│             prepare_batch.py       — 1-3 bosqichlarni papkadagi hamma video uchun
│             translate_batch.py     — 4-bosqichni (tarjima) hamma .srt uchun
│             normalize_srt_batch.py — 5-bosqichni (normalize) hamma tarjima uchun
utils/        ← umumiy yordamchilar: common.py (savollar, ffmpeg, vaqt), srt.py, locate_videos.py
│             collect_terms.py — normalize.json uchun atama shakllarini yig'ib beradi
assets/       ← videolar va ular yonidagi oraliq fayllar
```

Barcha komandalar **loyiha ildizidan** ishga tushiriladi:

```bash
.venv/bin/python steps/remove_audio.py
```

Xohlasangiz, modul ko'rinishida ham ishlaydi: `.venv/bin/python -m steps.remove_audio`

---

## 1. O'rnatish

### Talablar

- **ffmpeg** va **ffprobe** — `brew install ffmpeg`
- **Python 3.12** (loyihadagi `.venv` shu versiyada)
- **claude CLI** (4-bosqich, tarjima uchun) — `npm install -g @anthropic-ai/claude-code`, so'ng bir marta
  `claude` ni ishga tushirib tizimga kiring
- **CosyVoice** + **navoiy-tts** modellari (loyiha ichida)
- **demucs** — faqat kino rejimi uchun: `.venv/bin/pip install demucs`

### Python kutubxonalari

```bash
.venv/bin/pip install -U openai-whisper "setuptools<81"
```

> `large-v3-turbo` uchun `openai-whisper` ning kamida **20240930** versiyasi kerak
> (loyihada `20250625` ishlatilyapti). Eski versiyada `RuntimeError: Model
> large-v3-turbo not found` chiqadi.

> `setuptools<81` majburiy: yangi versiyalarda `pkg_resources` olib tashlangan, CosyVoice
> ishlatadigan `lightning` esa unga tayanadi. Aks holda `ModuleNotFoundError: No module named
> 'pkg_resources'` xatoligi chiqadi.

### Modellar

**Avtomatik yuklab olinadi** (birinchi ishga tushirishda):

- **whisper `large-v3-turbo`** — ~1.6 GB, `~/.cache/whisper` ga
- **demucs `htdemucs`** — ~300 MB (faqat kino rejimida)

**Qo'lda yuklab olinadi:**

- **CosyVoice2-0.5B** — ~4.5 GB, `CosyVoice/pretrained_models/CosyVoice2-0.5B/` ga (pastga qarang)
- **Navoiy checkpoint** — `navoiy-tts/emotion_600h_joint.pt`

#### CosyVoice2-0.5B ni yuklab olish

Agar `CosyVoice/` papkasi hali bo'lmasa, avval repozitoriyni klon qiling. `--recursive` **majburiy** —
`third_party/Matcha-TTS` submodul sifatida ulangan va usiz kod ishlamaydi:

```bash
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
```

So'ng modelni yuklab oling (ModelScope orqali — CosyVoice hujjatida tavsiya etilgan yo'l):

```bash
.venv/bin/python -c "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice2-0.5B', local_dir='CosyVoice/pretrained_models/CosyVoice2-0.5B')"
```

ModelScope sekin ishlasa yoki xatolik bersa, HuggingFace orqali:

```bash
.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('FunAudioLLM/CosyVoice2-0.5B', local_dir='CosyVoice/pretrained_models/CosyVoice2-0.5B')"
```

`modelscope` yoki `huggingface_hub` o'rnatilmagan bo'lsa:

```bash
.venv/bin/pip install modelscope huggingface_hub
```

**Tekshirish** — papka ichida kamida shu fayllar bo'lishi kerak:

```bash
ls CosyVoice/pretrained_models/CosyVoice2-0.5B/
```

```
CosyVoice-BlankEN/   campplus.onnx   cosyvoice2.yaml   flow.pt   hift.pt   llm.pt
speech_tokenizer_v2.onnx   flow.decoder.estimator.fp32.onnx   config.json
```

---

## 2. Ko'p video uchun

Bitta video uchun rejimni ishga tushirish yetarli ([COURSE.md](readme/COURSE.md) yoki
[MOVIE.md](readme/MOVIE.md)). Video ko'p bo'lganda esa quvur uch qismga bo'linadi va har biri butun papkani
qayta ishlaydi.

Papkalar ota papka nomidan aniqlanadi: `assets/docker` → `docker1`, `docker2`, ... Har uchala skript
`Start` va `End` oralig'ini so'raydi va **ikkala chegara ham ichiga kiradi**.

### 2.1. Tayyorgarlik (1-3 bosqichlar)

```bash
.venv/bin/python batches/prepare_batch.py
```

```
Path (video papkalari joylashgan ota papka): /path/to/assets/docker
Start (masalan 18 -> docker18 dan boshlanadi) [1]: 14
End (masalan 20 -> docker20 gacha, docker20 ham kiradi) [oxirigacha]: 20
```

Har bir papkadan `docker9/docker9.mp4` topiladi va `docker9-no-audio.mp4`, `docker9.wav`, `docker9.srt`
yasaladi. Uch natijasi ham tayyor papka o'tkazib yuboriladi, bitta video xato bersa quvur to'xtamaydi —
oxirida hisobot chiqadi.

> Bitta video uchun shu uch bosqich: `.venv/bin/python pipelines/prepare.py`

### 2.2. Tarjima (4-bosqich)

```bash
.venv/bin/python batches/translate_batch.py
```

```
Path (video papkalari joylashgan ota papka): /path/to/assets/docker
Start (masalan 14 -> docker14 dan boshlanadi) [1]: 14
End (masalan 20 -> docker20 gacha, docker20 ham kiradi) [oxirigacha]: 20
Qaysi tildan (til kodi) [en]: ⏎
Qaysi tilga (til kodi) [uz]: ⏎
```

```
docker14/docker14.srt  ->  docker14/docker14-uz.srt
docker15/docker15.srt  ->  docker15/docker15-uz.srt
```

- Tarjima allaqachon mavjud papka **o'tkazib yuboriladi** — har bir chaqiruv pullik. Qayta tarjima kerak
  bo'lsa, eski `-uz.srt` ni o'chiring.
- Oxirida hisobot, **jami narx** va umumiy vaqt chiqadi.
- Fayllar ketma-ket tarjima qilinadi (bir vaqtda bittadan).

### 2.3. Normalize (5-bosqich)

```bash
.venv/bin/python batches/normalize_srt_batch.py
```

```
Path (video papkalari joylashgan ota papka): /path/to/assets/docker
Start (masalan 14 -> docker14 dan boshlanadi) [1]: 14
End (masalan 20 -> docker20 gacha, docker20 ham kiradi) [oxirigacha]: 20
Tarjima tili (til kodi) [uz]: ⏎
Umumiy atamalar JSON fayli (/path/to/assets/docker/normalize.json) (o'tkazib yuborish uchun Enter): /path/to/assets/docker/normalize.json
Tayyor natijalar qayta hisoblansinmi? [ha/Yo'q]: ⏎
```

```
docker14/docker14-uz.srt  ->  docker14/docker14-uz-normalized.srt
```

- **Atamalar ro'yxati**: papka ichida `<papka nomi>-normalize.json` bo'lsa, aynan o'sha ishlatiladi (papkaga
  xos atamalar uchun); bo'lmasa — boshida so'ralgan umumiy JSON.
- Bosqich bepul va tez (hammasi lokal), shuning uchun `normalize.json` ni o'zgartirgach, oxirgi savolga `ha`
  deb javob berib hammasini qaytadan hisoblash mumkin.

### 2.4. Atamalar shakllarini yig'ish

5-bosqichdagi almashtirish faqat ikki tomonida bo'shliq bo'lgan so'zga qo'llaniladi, shuning uchun
`container'lar`, `container.` kabi shakllar `normalize.json` da alohida kalit bo'lishi kerak. Ularni qo'lda
terib chiqmaslik uchun:

```bash
.venv/bin/python utils/collect_terms.py
```

```
Path (video papkalari joylashgan ota papka): /path/to/assets/docker
normalize.json manzili [/path/to/assets/docker/normalize.json]: ⏎
Natija JSON fayllari qaysi papkaga saqlansin [/path/to/assets/docker/terms]: ⏎
```

Skript `<papka>/<papka nomi>-uz-normalized.srt` fayllarini o'qib, har bir atama uchun alohida fayl yaratadi —
masalan `terms/container.json`:

```json
{
  "container'lar": "konteyner'lar",
  "container.": "konteyner.",
  "containerda": "konteynerda"
}
```

Qiymat avtomatik to'ldiriladi. Manba sifatida **normalize qilingan** fayl olingani uchun u yerda faqat hali
almashtirilmagan shakllar qoladi — ya'ni natijadagi ro'yxat aynan `normalize.json` ga qo'shilishi kerak bo'lgan
yozuvlar bo'ladi.

---

## 3. Sozlamalar

Kodga tegmasdan, environment o'zgaruvchilari orqali:

### 3-bosqich (whisper)

| O'zgaruvchi             | Default            | Izoh                           |
|-------------------------|--------------------|--------------------------------|
| `WHISPER_MODEL`         | `large-v3-turbo`   | `large-v3` — sekinroq, aniqroq |
| `WHISPER_DEVICE`        | `cpu` / `cuda`     | `mps` ni sinab ko'rish mumkin  |
| `WHISPER_DOWNLOAD_ROOT` | `~/.cache/whisper` | model saqlanadigan papka       |

### 4-bosqich (Claude Code)

| O'zgaruvchi      | Default         | Izoh                        |
|------------------|-----------------|-----------------------------|
| `CLAUDE_MODEL`   | `claude-opus-5` | tarjima qiladigan model     |
| `CLAUDE_EFFORT`  | `high`          | effort darajasi             |
| `CLAUDE_TIMEOUT` | `3600`          | bitta chaqiruv uchun sekund |

### 6-bosqich (Navoiy TTS)

| O'zgaruvchi        | Default                     | Izoh                     |
|--------------------|-----------------------------|--------------------------|
| `NAVOIY_REFERENCE` | `navoiy-tts/demo/xurmo.wav` | qaysi ovozda gapirilishi |
| `NAVOIY_EMOTION`   | `calm`                      | hissiyot                 |
| `NAVOIY_SPEED`     | `1.0`                       | nutq tezligi             |
| `NAVOIY_SEED`      | `1986`                      | tasodifiylik urug'i      |

Mavjud hissiyotlar: `calm`, `happy`, `excited`, `sad`, `angry`, `nervous`, `scared`,
`surprised`, `whispers`, `warm`, `gentle`, `tired`, `sighs`, `sarcastic`

```bash
.venv/bin/python navoiy-tts/inference.py --list-emotions
```

Mavjud ovoz namunalari: `navoiy-tts/demo/` ichida — `xurmo.wav`, `calm_intro.wav`,
`warm_agent.wav`, `happy.wav`, `sad.wav`, `angry.wav`, `surprised.wav`, `long_form.wav`

### 1b-bosqich (demucs, faqat kino rejimi)

| O'zgaruvchi     | Default        | Izoh                      |
|-----------------|----------------|---------------------------|
| `DEMUCS_MODEL`  | `htdemucs`     | nutqni ajratish modeli    |
| `DEMUCS_DEVICE` | `cpu` / `cuda` | Apple Silicon uchun `mps` |

### Kod ichidagi konstantalar

| Fayl                       | Konstanta                    | Default          | Izoh                                                   |
|----------------------------|------------------------------|------------------|--------------------------------------------------------|
| `steps/remove_audio.py`    | `OUTPUT_SUFFIX`              | `-no-audio`      | ovozsiz video nomiga qo'shimcha                        |
| `steps/remove_vocals.py`   | `OUTPUT_SUFFIX`              | `-removed-vocal` | nutqsiz video nomiga qo'shimcha                        |
| `steps/generate_srt.py`    | `CONDITION_ON_PREVIOUS_TEXT` | `False`          | `True` — kontekst yaxshi, lekin takrorlanish xavfi bor |
| `steps/generate_audios.py` | `FIT_TO_TIMELINE`            | `True`           | audioni o'z oralig'iga sig'dirish                      |
| `steps/generate_audios.py` | `MAX_TEMPO`                  | `1.5`            | maksimal tezlashtirish                                 |
| `steps/merge_audios.py`    | `ORIGINAL_VOLUME`            | `1.0`            | videoda audio bo'lsa, uning balandligi                 |
| `steps/merge_audios.py`    | `OUTPUT_SUFFIX`              | `-result`        | yakuniy video nomiga qo'shimcha                        |

---

## 4. Tez-tez uchraydigan savollar

**Jarayon uzilib qoldi, boshidan boshlash kerakmi?**
Yo'q. Har bir bosqich tayyor natijani qayta hisoblamaydi — rejimni qaytadan ishga tushiring.

**O'zbekcha ovoz yoqmadi, boshqasini sinab ko'rmoqchiman.**

```bash
rm -rf /path/to/docker/audios
NAVOIY_REFERENCE=navoiy-tts/demo/warm_agent.wav .venv/bin/python steps/generate_audios.py
```

**Videoning fon musiqasi kerak bo'lsa-chi?**
Kino rejimini oling: [readme/MOVIE.md](readme/MOVIE.md). U 1-bosqichda demucs orqali faqat odam nutqini olib
tashlaydi va fonni joyida qoldiradi.

**O'zbekcha nutq keyingi jumla ustiga chiqib ketyapti.**
O'zbekcha matn inglizchadan uzunroq bo'ladi. `steps/generate_audios.py` da `MAX_TEMPO` ni `1.8`
ga ko'taring yoki `NAVOIY_SPEED=1.15` bilan generatsiya qiling.

**TTS inglizcha atamani noto'g'ri o'qiyapti.**
Uni `normalize.json` ga fonetik ko'rinishda qo'shing (`"docker": "do'ker"`). Model ichiga yangi so'z
"o'rgatib" bo'lmaydi — CosyVoice2 da leksikon qatlami yo'q, shuning uchun yagona yo'l shu.

**`ModuleNotFoundError: No module named 'pkg_resources'`**

```bash
.venv/bin/pip install "setuptools<81"
```
