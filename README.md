# Video tarjimon: ingliz → o'zbek dublyaj

Ingliz tilidagi videoni o'zbek tilida gapiriladigan variantga o'tkazish uchun mo'ljallangan 7 bosqichli quvur
(pipeline). Har bir bosqich alohida faylda va uni **mustaqil ravishda** ham, `modes/` dagi rejimlar orqali
**ketma-ket** ham ishga tushirish mumkin.

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

1-bosqich **rejimga qarab** tanlanadi: `modes/course.py` → `1a`, `modes/movie.py` → `1b`. Qolgan bosqichlar
ikkalasida ham bir xil.

> **Diqqat:** 2-bosqich transkripsiya uchun **asl** videodan audio oladi (nutq faqat o'sha yerda),
> 7-bosqich esa 1-bosqichda tayyorlangan videoni ishlatadi.

> Kurslar uchun orqa fondagi musiqa/effektlar kerak emas, shuning uchun `course.py` da 1-bosqich audio oqimini
> butunlay tashlab yuboradi. Kinoda esa fon muhim — `movie.py` demucs orqali faqat nutqni ajratib oladi.

### Loyiha strukturasi

```
steps/        ← quvurning alohida bosqichlari (har birini mustaqil ishga tushirsa bo'ladi)
modes/        ← tayyor rejimlar: butun quvurni ma'lum bir video turi uchun bajaradi
│             course.py — kurs videolari uchun (fon ovozi tashlab yuboriladi)
│             movie.py  — kinolar uchun (fon musiqasi va effektlar saqlanadi)
pipelines/    ← bir nechta bosqichni ketma-ket bajaradigan qisqartirilgan quvurlar
│             prepare.py — tarjimadan oldingi tayyorgarlik (1-3 bosqichlar)
batches/      ← bir nechta video uchun quvurlarni ketma-ket ishga tushiruvchi kodlar
│             prepare_batch.py      — prepare.py ni papkadagi hamma video uchun bajaradi
│             translate_batch.py    — 4-bosqichni (tarjima) hamma .srt uchun bajaradi
│             normalize_srt_batch.py — 5-bosqichni (normalize) hamma tarjima uchun bajaradi
utils/        ← umumiy yordamchilar: common.py (savollar, ffmpeg, vaqt), srt.py, locate_videos.py
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

## 2. Eng oson yo'l: `modes/` rejimlari

Rejim barcha bosqichlarni ketma-ket bajaradi va faqat kerakli joyda savol beradi. Video turiga qarab birini tanlang:

| Rejim              | 1-bosqichda nima bo'ladi                          | Qachon                                        |
|--------------------|---------------------------------------------------|-----------------------------------------------|
| `modes/course.py`  | audio oqimi butunlay tashlanadi (`remove_audio`)   | kurs, ma'ruza — fon ovozi kerak emas          |
| `modes/movie.py`   | faqat odam nutqi olinadi (`remove_vocals`, demucs) | kino, film — fon musiqasi va effektlar muhim  |

### `modes/course.py` — kurs videolari uchun

```bash
.venv/bin/python modes/course.py
```

`/path/to/docker/docker.mp4` berilganda quyidagi fayllar shu tartibda ishga tushadi:

```
[1/7] steps/remove_audio.py      docker.mp4                 -> docker-no-audio.mp4
[2/7] steps/extract_audio.py     docker.mp4                 -> docker.wav
[3/7] steps/generate_srt.py      docker.wav                 -> docker.srt
[4/7] steps/translate_srt.py     docker.srt                 -> docker-uz.srt            (claude -p)
[5/7] steps/normalize_srt.py     docker-uz.srt              -> docker-uz-normalized.srt
[6/7] steps/generate_audios.py   docker-uz-normalized.srt   -> audios/*.wav
[7/7] steps/merge_audios.py      docker-no-audio.mp4 + audios/  -> docker-result.mp4
```

Yakuniy videoda faqat o'zbekcha nutq eshitiladi — asl ovozdan hech narsa qolmaydi.

### `modes/movie.py` — kinolar uchun

```bash
.venv/bin/python modes/movie.py
```

`/path/to/movie/movie.mp4` berilganda quyidagi fayllar shu tartibda ishga tushadi:

```
[1/7] steps/remove_vocals.py     movie.mp4                  -> movie-removed-vocal.mp4  (demucs)
[2/7] steps/extract_audio.py     movie.mp4                  -> movie.wav
[3/7] steps/generate_srt.py      movie.wav                  -> movie.srt
[4/7] steps/translate_srt.py     movie.srt                  -> movie-uz.srt             (claude -p)
[5/7] steps/normalize_srt.py     movie-uz.srt               -> movie-uz-normalized.srt
[6/7] steps/generate_audios.py   movie-uz-normalized.srt    -> audios/*.wav
[7/7] steps/merge_audios.py      movie-removed-vocal.mp4 + audios/  -> movie-result.mp4
```

Farqi faqat **1-bosqichda**: `remove_vocals.py` audio oqimini tashlamaydi, balki demucs orqali undan odam
nutqini ajratib oladi va fon (musiqa, effektlar) qolgan videoni yasaydi. Shu sababli 7-bosqichda
`merge_audios.py` videoda audio oqimi borligini ko'radi va o'sha fonni o'zbekcha nutq bilan aralashtiradi —
balandligi `ORIGINAL_VOLUME` (default `1.0`) bilan boshqariladi.

1-bosqich sekin: demucs CPU da taxminan real vaqtda ishlaydi (1 soatlik kino ≈ 1 soat). Tezlashtirish uchun:

```bash
DEMUCS_DEVICE=mps .venv/bin/python modes/movie.py
```

### Ikkalasiga ham tegishli

Rejim ishga tushgach faqat bitta savol beriladi:

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
```

Shundan keyin dastur o'zi ishlaydi. Faqat quyidagi joylarda to'xtaydi:

1. `.srt` allaqachon mavjud bo'lsa — qayta generatsiya qilishni so'raydi (Enter = yo'q)
2. **4-bosqich** — tarjima allaqachon mavjud bo'lsa, qayta tarjima qilishni so'raydi (Enter = yo'q)
3. **5-bosqich** — atamalar JSON faylini so'raydi (kerak bo'lmasa Enter)
4. faqat `movie.py`: `-removed-vocal` video allaqachon mavjud bo'lsa, qayta yasashni so'raydi (Enter = yo'q)

---

## 2.1. Ko'p video uchun: `pipelines/prepare.py` va `batches/prepare_batch.py`

Tarjimadan oldingi tayyorgarlik (1-3 bosqichlar: ovozsiz video + `.wav` + inglizcha `.srt`)
alohida ajratilgan: shu uch bosqich tugagach, tarjima va TTS bosqichlariga o'tiladi.

**Bitta video uchun** — barcha savollar boshida bir marta so'raladi:

```bash
.venv/bin/python pipelines/prepare.py
```

**Bir nechta video uchun** — bitta komanda bilan ketma-ket:

```bash
.venv/bin/python batches/prepare_batch.py
```

```
Path (video papkalari joylashgan ota papka): /path/to/assets/docker
Start (masalan 18 -> docker18 dan boshlanadi) [1]: 14
End (masalan 20 -> docker20 gacha, docker20 ham kiradi) [oxirigacha]: 20
```

Bu misolda `docker14` dan `docker20` gacha bo'lgan papkalar bajariladi — **ikkala chegara ham ichiga kiradi**.
`End` savolida Enter bossangiz, oxirigacha davom etadi; `Start` da Enter (yoki `0`) — boshidan.

Har bir papka nomidan uning ichidagi fayllar aniqlanadi (`docker9` → `docker9/docker9.mp4`,
`docker9-no-audio.mp4`, `docker9.wav`, `docker9.srt`, til `en`). Papkalar nomidagi **raqam**
bo'yicha tartiblanadi (`docker2` → `docker10` → `docker100`), shuning uchun `Start` va `End` aynan shu raqamga
qaraydi. Uch natijasi ham tayyor papka o'tkazib yuboriladi, bitta video xato bersa quvur to'xtamaydi — oxirida
hisobot chiqadi.

---

## 2.2. Ko'p `.srt` ni tarjima qilish: `batches/translate_batch.py`

Tayyorgarlikdan keyingi qadam — 4-bosqichni (tarjima) bir necha papka uchun birdan bajarish:

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

Ichki papkalar nomi **ota papka nomidan** aniqlanadi (`docker` → `docker1`, `docker2`, ...), har birida
`<papka nomi>.srt` qidiriladi va yoniga `<papka nomi>-uz.srt` yoziladi:

```
docker14/docker14.srt  ->  docker14/docker14-uz.srt
docker15/docker15.srt  ->  docker15/docker15-uz.srt
```

- Tarjima allaqachon mavjud papka **o'tkazib yuboriladi** — har bir chaqiruv pullik. Qayta tarjima kerak bo'lsa,
  eski `-uz.srt` ni o'chiring.
- Bitta fayl xato bersa quvur to'xtamaydi; oxirida hisobot, **jami narx** va umumiy vaqt chiqadi.
- Nomi ota papka nomi bilan boshlanmaydigan yoki ichida `.srt` bo'lmagan papkalar boshida ro'yxat qilib
  ko'rsatiladi.
- Fayllar ketma-ket tarjima qilinadi (bir vaqtda bittadan).

---

## 2.3. Ko'p `.srt` ni normalize qilish: `batches/normalize_srt_batch.py`

Tarjimadan keyingi qadam — 5-bosqichni (TTS uchun normalize) bir necha papka uchun birdan bajarish:

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

Har bir papkada `<papka nomi>-uz.srt` qidiriladi va yoniga `-normalized` qo'shimchasi bilan yoziladi:

```
docker14/docker14-uz.srt  ->  docker14/docker14-uz-normalized.srt
```

- **Atamalar ro'yxati**: papka ichida `<papka nomi>-normalize.json` bo'lsa, aynan o'sha ishlatiladi (papkaga xos
  atamalar uchun); bo'lmasa — boshida so'ralgan umumiy JSON. Ikkalasi ham bo'lmasa, faqat sonlar/sanalar so'zga
  aylantiriladi.
- Bosqich bepul va tez (hammasi lokal), shuning uchun `normalize.json` ni o'zgartirgach, oxirgi savolga `ha` deb
  javob berib hammasini qaytadan hisoblash mumkin.
- Bitta fayl xato bersa (masalan buzuq JSON) quvur to'xtamaydi — oxirida hisobot chiqadi.

---

## 3. Bosqichma-bosqich: `/path/to/docker/docker.mp4` misolida

Quyida har bir faylni alohida ishga tushirish tartibi. Barcha savollarda kvadrat qavs ichidagi qiymat — default;
**Enter** bosish kifoya.

### 1-bosqich — videodan audioni olib tashlash

```bash
.venv/bin/python steps/remove_audio.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
Ovozsiz video qayerga saqlansin [/path/to/docker/docker-no-audio.mp4]: ⏎
```

**Natija:** `/path/to/docker/docker-no-audio.mp4` — tasvir o'zgarmaydi (`-c:v copy`), audio oqimi esa umuman yo'q. Bir
necha soniyada tugaydi.

#### Muqobil: fon ovozini saqlab qolish (`steps/remove_vocals.py`)

Agar videoning fon ovozi (musiqa, effektlar) kerak bo'lsa, audioni butunlay tashlash o'rniga faqat **odam nutqini**
olib tashlash mumkin. Buni demucs qiladi:

```bash
.venv/bin/python steps/remove_vocals.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
Nutqsiz video qayerga saqlansin [/path/to/docker/docker-removed-vocal.mp4]: ⏎
```

**Natija:** `/path/to/docker/docker-removed-vocal.mp4` — tasvir o'zgarmaydi, ovozda esa inglizcha nutq qolmaydi,
faqat fon tovushlari eshitiladi. Oraliq `.wav` fayllar avtomatik o'chiriladi (fon audiosini saqlab qolish uchun
`background_audio` argumentini bering).

Buning uchun demucs kerak (model birinchi ishlatilganda ~300 MB yuklab olinadi):

```bash
.venv/bin/pip install demucs
```

Bu bosqich **sekin**: CPU da real vaqtdan ~1x, Apple Silicon'da tezroq bo'lishi mumkin:

```bash
DEMUCS_DEVICE=mps .venv/bin/python steps/remove_vocals.py
```

> Kurs videolarida fon ovozi odatda kerak emas, shuning uchun `modes/course.py` va `pipelines/prepare.py`
> `remove_audio.py` ni ishlatadi. Bu bosqichni butun quvur bilan birga ishlatmoqchi bo'lsangiz,
> `modes/movie.py` rejimini oling — u aynan shu faylni chaqiradi.

---

### 2-bosqich — videodan audio ajratish

```bash
.venv/bin/python steps/extract_audio.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
Audio fayl qayerga saqlansin [/path/to/docker/docker.wav]: ⏎
```

**Natija:** `/path/to/docker/docker.wav` (16 kHz mono — whisper uchun optimal)

---

### 3-bosqich — transkripsiya (inglizcha `.srt`)

```bash
.venv/bin/python steps/generate_srt.py
```

```
Audio fayl manzilini kiriting (/path/to/docker/docker.wav): /path/to/docker/docker.wav
Transkripsiya .srt fayli qayerga saqlansin [/path/to/docker/docker.srt]: ⏎
Audiodagi nutq tili (auto — o'zi aniqlaydi) [en]: ⏎
```

**Natija:** `/path/to/docker/docker.srt`

Til savolida Enter bosilsa `en` olinadi. Boshqa til uchun `ru`, `uz` kabi kod kiriting;
`auto` deb yozsangiz, whisper tilni o'zi aniqlaydi.

Default model — `large-v3-turbo`: `large-v3` ning qisqartirilgan dekoderli varianti, bir necha barobar tez ishlaydi va
transkripsiya sifati deyarli o'zgarmaydi. Aniqroq natija kerak bo'lsa (masalan sifati past, shovqinli yozuv), to'liq
modelga qaytish mumkin:

```bash
WHISPER_MODEL=large-v3 .venv/bin/python steps/generate_srt.py
```

---

### 4-bosqich — tarjima (Claude Code headless)

```bash
.venv/bin/python steps/translate_srt.py
```

```
Tarjima qilinadigan .srt fayl manzilini kiriting: /path/to/docker/docker.srt
Tarjima qilingan .srt fayl qayerga saqlansin [/path/to/docker/docker-uz.srt]: ⏎
  Yo'nalish: en -> uz | 59 ta subtitr
  Model: claude-opus-5 (effort=high) — bu biroz vaqt oladi...
  29 ta subtitr yozildi (1 daqiqa 12 soniya, $0.4137).
```

**Natija:** `/path/to/docker/docker-uz.srt`

Butun `.srt` matni `claude -p` ga prompt sifatida beriladi va model tayyor `.srt` qaytaradi. Prompt bloklarni
birlashtirishga ruxsat bergani uchun natijada bloklar soni kamayishi normal.

Talab: `claude` CLI o'rnatilgan va tizimga kirilgan bo'lishi kerak:

```bash
npm install -g @anthropic-ai/claude-code
```

Tarjima allaqachon mavjud bo'lsa, qayta tarjima qilish so'raladi (Enter = yo'q) — chunki har bir chaqiruv
pullik. Model faqat matn qaytarishi uchun barcha tool'lar o'chirilgan va sessiya saqlanmaydi.

Sozlamalar (environment o'zgaruvchilari):

| O'zgaruvchi      | Default          | Izoh                              |
|------------------|------------------|-----------------------------------|
| `CLAUDE_MODEL`   | `claude-opus-5`  | tarjima qiladigan model           |
| `CLAUDE_EFFORT`  | `high`           | effort darajasi                   |
| `CLAUDE_TIMEOUT` | `3600`           | bitta chaqiruv uchun sekund       |

```bash
CLAUDE_MODEL=claude-sonnet-5 .venv/bin/python steps/translate_srt.py
```

---

### 5-bosqich — matnni TTS uchun normalize qilish

```bash
.venv/bin/python steps/normalize_srt.py
```

```
Tarjima qilingan .srt fayl manzilini kiriting (/path/to/docker/docker-uz.srt): /path/to/docker/docker-uz.srt
Normalize qilingan .srt qayerga saqlansin [/path/to/docker/docker-uz-normalized.srt]: ⏎
Atamalar JSON fayli manzilini kiriting (/path/to/docker/normalize.json) (o'tkazib yuborish uchun Enter): /path/to/docker/normalize.json
```

**Natija:** `/path/to/docker/docker-uz-normalized.srt`

Bu bosqich ikki ishni bajaradi:

**1) Sonlar, sanalar va vaqtni so'zga aylantiradi** (`uztts.normalize`) — TTS raqamlarni o'qiy olmaydi:

```
Bugun 16.07.2026, soat 14:30 da uchrashamiz.
→ Bugun o'n olti iyul ikki ming yigirma olti, soat o'n to'rt o'ttiz da uchrashamiz.
```

**2) Inglizcha atamalarni almashtiradi** (ixtiyoriy) — tarjima qilinmaydigan atamalarni TTS noto'g'ri talaffuz qiladi.
Ro'yxat JSON faylda beriladi:

```json
{
  "docker": "do'ker",
  "kubernetes": "kubernites",
  "container": "konteyner"
}
```

Namuna sifatida `terms.example.json` fayli bor — uni nusxalab, o'zingizga moslang:

```bash
cp terms.example.json /path/to/docker/normalize.json
```

Almashtirish katta-kichik harfga qaramaydi va faqat **butun so'zlarga** qo'llaniladi —
`Docker` → `do'ker`, lekin `dockerfile` tegilmaydi.

Atamalar kerak bo'lmasa, savolda shunchaki **Enter** bosing — faqat normalize bajariladi.

---

### 6-bosqich — o'zbekcha audiolar (TTS)

```bash
.venv/bin/python steps/generate_audios.py
```

```
Normalize qilingan .srt fayl manzilini kiriting (/path/to/docker/docker-uz-normalized.srt): /path/to/docker/docker-uz-normalized.srt
Audiolar qaysi papkaga saqlansin [/path/to/docker/audios]: ⏎
```

**Natija:** `/path/to/docker/audios/00-00-01-500.wav`, `00-00-04-200.wav`, …

Fayl nomi — subtitrning **boshlanish vaqti** (soat-daqiqa-soniya-millisekund). 7-bosqich audioni videoga aynan shu nom
bo'yicha joylashtiradi, shuning uchun fayllarni qayta nomlamang.

Bir necha muhim xususiyat:

- Model **bir marta** yuklanadi, barcha segmentlar shu jarayonda generatsiya qilinadi
- Papkada tayyor fayl bo'lsa, u qayta generatsiya qilinmaydi (uzilgan jarayonni davom ettirish mumkin). Ovozni butunlay
  yangilash uchun: `rm -rf /path/to/docker/audios`
- Audio o'z oralig'iga sig'masa, avtomatik tezlashtiriladi (maksimum 1.5x)

---

### 7-bosqich — o'zbekcha audiolarni biriktirish

```bash
.venv/bin/python steps/merge_audios.py
```

```
Ovozsiz video fayl manzilini kiriting (/path/to/docker/docker-no-audio.mp4): /path/to/docker/docker-no-audio.mp4
Audiolar joylashgan papka manzilini kiriting [/path/to/docker/audios]: ⏎
```

> **Diqqat:** bu yerda asl `video.mp4` emas, 1-bosqichdan chiqqan `video-no-audio.mp4` (yoki `movie.py` da
> `video-removed-vocal.mp4`) berilishi kerak. Aks holda inglizcha nutq qaytib qo'shiladi.

**Natija:** `/path/to/docker/docker-result.mp4` — tayyor dublyaj qilingan video

> Nom asl video nomidan hosil bo'ladi: `-no-audio` va `-removed-vocal` qo'shimchalari tashlab yuborilib,
> o'rniga `-result` qo'yiladi (`docker-no-audio.mp4` → `docker-result.mp4`). Rejimlar ham xuddi shu nomni beradi.

---

## 4. Fayllar xaritasi

`/path/to/docker/docker.mp4` uchun `modes/course.py` oxirida quyidagilar hosil bo'ladi:

```
/path/to/docker/
├── docker.mp4                 ← manba
├── docker-no-audio.mp4        ← 1-bosqich (ovozsiz video)
├── docker.wav                 ← 2-bosqich (16 kHz mono)
├── docker.srt                 ← 3-bosqich (inglizcha)
├── docker-uz.srt              ← 4-bosqich (o'zbekcha, claude -p)
├── normalize.json             ← atamalar ro'yxati (ixtiyoriy, o'zingiz yaratasiz)
├── docker-uz-normalized.srt   ← 5-bosqich (TTS uchun tayyorlangan)
├── audios/                    ← 6-bosqich
│   ├── 00-00-01-500.wav
│   └── 00-00-04-200.wav
└── docker-result.mp4          ← 7-bosqich (NATIJA)
```

`modes/movie.py` da bitta fayl boshqacha nomlanadi: `docker-no-audio.mp4` o'rniga
`docker-removed-vocal.mp4` (ichida fon ovozi saqlangan). Qolgan fayllar bir xil.

---

## 5. Sozlamalar

Kodga tegmasdan, environment o'zgaruvchilari orqali:

### 3-bosqich (whisper)

| O'zgaruvchi             | Default            | Izoh                           |
|-------------------------|--------------------|--------------------------------|
| `WHISPER_MODEL`         | `large-v3-turbo`   | `large-v3` — sekinroq, aniqroq |
| `WHISPER_DEVICE`        | `cpu` / `cuda`     | `mps` ni sinab ko'rish mumkin  |
| `WHISPER_DOWNLOAD_ROOT` | `~/.cache/whisper` | model saqlanadigan papka       |

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

### Ixtiyoriy bosqich (demucs)

| O'zgaruvchi     | Default        | Izoh                      |
|-----------------|----------------|---------------------------|
| `DEMUCS_MODEL`  | `htdemucs`     | nutqni ajratish modeli    |
| `DEMUCS_DEVICE` | `cpu` / `cuda` | Apple Silicon uchun `mps` |

### Kod ichidagi konstantalar

| Fayl                       | Konstanta                    | Default     | Izoh                                                   |
|----------------------------|------------------------------|-------------|--------------------------------------------------------|
| `steps/remove_audio.py`    | `OUTPUT_SUFFIX`              | `-no-audio` | ovozsiz video nomiga qo'shimcha                        |
| `steps/remove_vocals.py`   | `OUTPUT_SUFFIX`              | `-removed-vocal` | nutqsiz video nomiga qo'shimcha                   |
| `steps/generate_srt.py`    | `CONDITION_ON_PREVIOUS_TEXT` | `False`     | `True` — kontekst yaxshi, lekin takrorlanish xavfi bor |
| `steps/generate_audios.py` | `FIT_TO_TIMELINE`            | `True`      | audioni o'z oralig'iga sig'dirish                      |
| `steps/generate_audios.py` | `MAX_TEMPO`                  | `1.5`       | maksimal tezlashtirish                                 |
| `steps/merge_audios.py`    | `ORIGINAL_VOLUME`            | `1.0`       | videoda audio bo'lsa, uning balandligi                 |

---

## 6. Tez-tez uchraydigan savollar

**Jarayon uzilib qoldi, boshidan boshlash kerakmi?**
Yo'q. Har bir bosqich tayyor natijani qayta hisoblamaydi — `modes/course.py` ni qaytadan ishga tushiring.

**O'zbekcha ovoz yoqmadi, boshqasini sinab ko'rmoqchiman.**

```bash
rm -rf /path/to/docker/audios
NAVOIY_REFERENCE=navoiy-tts/demo/warm_agent.wav .venv/bin/python steps/generate_audios.py
```

**Videoning fon musiqasi kerak bo'lsa-chi?**
`modes/course.py` o'rniga `modes/movie.py` ni ishga tushiring — u 1-bosqichda `steps/remove_vocals.py` ni chaqiradi,
ya'ni demucs orqali faqat odam nutqini olib tashlaydi va fonni joyida qoldiradi. Fon baland tuyulsa,
`steps/merge_audios.py` dagi `ORIGINAL_VOLUME` ni `0.3`–`0.6` ga tushiring.

**O'zbekcha nutq keyingi jumla ustiga chiqib ketyapti.**
O'zbekcha matn inglizchadan uzunroq bo'ladi. `steps/generate_audios.py` da `MAX_TEMPO` ni `1.8`
ga ko'taring yoki `NAVOIY_SPEED=1.15` bilan generatsiya qiling.

**`ModuleNotFoundError: No module named 'pkg_resources'`**

```bash
.venv/bin/pip install "setuptools<81"
```
