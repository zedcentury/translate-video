# Video tarjimon: ingliz → o'zbek dublyaj

Ingliz tilidagi videoni o'zbek tilida gapiriladigan variantga o'tkazish uchun mo'ljallangan
8 bosqichli quvur (pipeline). Har bir bosqich alohida faylda va uni **mustaqil ravishda** ham,
`main.py` orqali **ketma-ket** ham ishga tushirish mumkin.

| # | Fayl | Nima qiladi | Vosita |
|---|------|-------------|--------|
| 1 | `step1_extract_audio.py` | Videodan audio ajratib oladi | ffmpeg |
| 2 | `step2_generate_srt.py` | Audiodan inglizcha `.srt` yasaydi | openai-whisper `large-v3` |
| 3 | `step3_translate_srt.py` | `.srt` ni o'zbekchaga tarjima qiladi | **qo'lda** (LLM) |
| 4 | `step4_normalize_srt.py` | Sonlar/sanalarni so'zga aylantiradi, atamalarni almashtiradi | uztts |
| 5 | `step5_generate_audios.py` | Har bir subtitr uchun audio generatsiya qiladi | Navoiy TTS (CosyVoice2) |
| 6 | `step6_remove_vocals.py` | Asl ovozdan odam nutqini olib tashlaydi | demucs |
| 7 | `step7_replace_audio.py` | Video ovozini nutqsiz fonga almashtiradi | ffmpeg |
| 8 | `step8_merge_audios.py` | O'zbekcha audiolarni timestamp bo'yicha qo'yadi | ffmpeg |

---

## 1. O'rnatish

### Talablar

- **ffmpeg** va **ffprobe** — `brew install ffmpeg`
- **Python 3.12** (loyihadagi `.venv` shu versiyada)
- **CosyVoice** + **navoiy-tts** modellari (loyiha ichida)

### Python kutubxonalari

```bash
.venv/bin/pip install openai-whisper demucs "setuptools<81"
```

> `setuptools<81` majburiy: yangi versiyalarda `pkg_resources` olib tashlangan, CosyVoice
> ishlatadigan `lightning` esa unga tayanadi. Aks holda `ModuleNotFoundError: No module named
> 'pkg_resources'` xatoligi chiqadi.

### Modellar

**Avtomatik yuklab olinadi** (birinchi ishga tushirishda):

- **whisper `large-v3`** — ~3 GB, `~/.cache/whisper` ga
- **demucs `htdemucs`** — ~300 MB, `~/.cache/torch/hub` ga

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

## 2. Eng oson yo'l: `main.py`

Barcha bosqichlarni ketma-ket bajaradi va faqat kerakli joyda savol beradi:

```bash
.venv/bin/python main.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
```

Shundan keyin dastur o'zi ishlaydi. Faqat quyidagi joylarda to'xtaydi:

1. `.srt` allaqachon mavjud bo'lsa — qayta generatsiya qilishni so'raydi (Enter = yo'q)
2. **3-bosqich** — o'zbekcha tarjimani qo'lda tayyorlashingizni kutadi (pastga qarang)
3. **4-bosqich** — atamalar JSON faylini so'raydi (kerak bo'lmasa Enter)
4. `-background.wav` mavjud bo'lsa — qayta ajratishni so'raydi (Enter = yo'q)

---

## 3. Bosqichma-bosqich: `/path/to/docker/docker.mp4` misolida

Quyida har bir faylni alohida ishga tushirish tartibi. Barcha savollarda kvadrat qavs ichidagi
qiymat — default; **Enter** bosish kifoya.

### 1-bosqich — videodan audio ajratish

```bash
.venv/bin/python step1_extract_audio.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
Audio fayl qayerga saqlansin [/path/to/docker/docker.wav]: ⏎
```

**Natija:** `/path/to/docker/docker.wav` (16 kHz mono — whisper uchun optimal)

---

### 2-bosqich — transkripsiya (inglizcha `.srt`)

```bash
.venv/bin/python step2_generate_srt.py
```

```
Audio fayl manzilini kiriting (/path/to/docker/docker.wav): /path/to/docker/docker.wav
Transkripsiya .srt fayli qayerga saqlansin [/path/to/docker/docker.srt]: ⏎
Audiodagi nutq tili (auto — o'zi aniqlaydi) [en]: ⏎
```

**Natija:** `/path/to/docker/docker.srt`

Til savolida Enter bosilsa `en` olinadi. Boshqa til uchun `ru`, `uz` kabi kod kiriting;
`auto` deb yozsangiz, whisper tilni o'zi aniqlaydi.

CPU'da `large-v3` real vaqtdan sekinroq ishlaydi — 30 daqiqalik video ~40-60 daqiqa oladi.
Tezroq variant:

```bash
WHISPER_MODEL=large-v3-turbo .venv/bin/python step2_generate_srt.py
```

---

### 3-bosqich — tarjima (QO'LDA)

```bash
.venv/bin/python step3_translate_srt.py
```

```
Tarjima qilinadigan .srt fayl manzilini kiriting: /path/to/docker/docker.srt
Tarjima qilingan .srt fayl qayerga saqlansin [/path/to/docker/docker-uz.srt]: ⏎
  Tarjima hozircha qo'lda bajariladi. docker-uz.srt tayyormi? [ha/yo'q]:
```

Bu paytda `/path/to/docker/docker.srt` faylini Claude / ChatGPT / Gemini ga yuklab, quyidagi prompt bilan
tarjima qildiring, natijani `/path/to/docker/docker-uz.srt` nomi bilan saqlang, so'ng `ha` deb javob bering:

> Yuklangan .srt faylni o'zbek tiliga (lotin) tarjima qil. Timestamp'lar o'zgarmasin, format
> saqlansin. Gap yoki atama ikki blokka bo'linib qolgan joylarda bloklarni birlashtirishga ruxsat —
> birlashgan blok birinchi bo'lakning boshi va oxirgi bo'lakning oxiri vaqtini olsin, keyin qayta
> raqamla. Texnik atamalar asl holida qolsin. Uslub — jonli, o'qituvchi so'zlayotgandek.
> Transkripsiya xatolarini to'g'irlab tarjima qil. Natijani .srt fayl ko'rinishida ber.

**Natija:** `/path/to/docker/docker-uz.srt`

---

### 4-bosqich — matnni TTS uchun normalize qilish

```bash
.venv/bin/python step4_normalize_srt.py
```

```
Tarjima qilingan .srt fayl manzilini kiriting (/path/to/docker/docker-uz.srt): /path/to/docker/docker-uz.srt
Normalize qilingan .srt qayerga saqlansin [/path/to/docker/docker-uz-normalized.srt]: ⏎
Atamalar JSON fayli manzilini kiriting (/path/to/docker/normalize.json) (o'tkazib yuborish uchun Enter): /path/to/docker/normalize.json
```

**Natija:** `/path/to/docker/docker-uz-normalized.srt`

Bu bosqich ikki ishni bajaradi:

**1) Sonlar, sanalar va vaqtni so'zga aylantiradi** (`uztts.normalize`) — TTS raqamlarni o'qiy
olmaydi:

```
Bugun 16.07.2026, soat 14:30 da uchrashamiz.
→ Bugun o'n olti iyul ikki ming yigirma olti, soat o'n to'rt o'ttiz da uchrashamiz.
```

**2) Inglizcha atamalarni almashtiradi** (ixtiyoriy) — tarjima qilinmaydigan atamalarni TTS
noto'g'ri talaffuz qiladi. Ro'yxat JSON faylda beriladi:

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

### 5-bosqich — o'zbekcha audiolar (TTS)

```bash
.venv/bin/python step5_generate_audios.py
```

```
Normalize qilingan .srt fayl manzilini kiriting (/path/to/docker/docker-uz-normalized.srt): /path/to/docker/docker-uz-normalized.srt
Audiolar qaysi papkaga saqlansin [/path/to/docker/audios]: ⏎
```

**Natija:** `/path/to/docker/audios/00-00-01-500.wav`, `00-00-04-200.wav`, …

Fayl nomi — subtitrning **boshlanish vaqti** (soat-daqiqa-soniya-millisekund). 8-bosqich audioni
videoga aynan shu nom bo'yicha joylashtiradi, shuning uchun fayllarni qayta nomlamang.

Bir necha muhim xususiyat:

- Model **bir marta** yuklanadi, barcha segmentlar shu jarayonda generatsiya qilinadi
- Papkada tayyor fayl bo'lsa, u qayta generatsiya qilinmaydi (uzilgan jarayonni davom ettirish
  mumkin). Ovozni butunlay yangilash uchun: `rm -rf /path/to/docker/audios`
- Audio o'z oralig'iga sig'masa, avtomatik tezlashtiriladi (maksimum 1.5x)

---

### 6-bosqich — nutqni fondan ajratish

```bash
.venv/bin/python step6_remove_vocals.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
Fon audiosi qayerga saqlansin [/path/to/docker/docker-background.wav]: ⏎
```

**Natija:** `/path/to/docker/docker-background.wav` — musiqa va effektlar qoladi, inglizcha nutq yo'qoladi

CPU'da ~0.5x real vaqt (30 daqiqalik video ≈ 15-20 daqiqa). Apple Silicon'da tezroq:

```bash
DEMUCS_DEVICE=mps .venv/bin/python step6_remove_vocals.py
```

---

### 7-bosqich — video ovozini fonga almashtirish

```bash
.venv/bin/python step7_replace_audio.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
Fon audiosi manzilini kiriting [/path/to/docker/docker-background.wav]: ⏎
Natijaviy video qayerga saqlansin [/path/to/docker/docker-background.mp4]: ⏎
```

**Natija:** `/path/to/docker/docker-background.mp4` — tasvir o'zgarmaydi (`-c:v copy`), ovozda esa
inglizcha nutq qolmagan

---

### 8-bosqich — o'zbekcha audiolarni biriktirish

```bash
.venv/bin/python step8_merge_audios.py
```

```
Vokal o'chirilgan video fayl manzilini kiriting (/path/to/docker/docker-background.mp4): /path/to/docker/docker-background.mp4
Audiolar joylashgan papka manzilini kiriting [/path/to/docker/audios]: ⏎
```

> **Diqqat:** bu yerda asl `video.mp4` emas, 7-bosqichdan chiqqan `video-background.mp4`
> berilishi kerak. Aks holda inglizcha nutq qaytib qo'shiladi.

**Natija:** `/path/to/docker/docker-background-uz.mp4` — tayyor dublyaj qilingan video

> `main.py` orqali ishlatilganda natija `/path/to/docker/docker-uz.mp4` deb nomlanadi.

---

## 4. Fayllar xaritasi

`/path/to/docker/docker.mp4` uchun quvur oxirida quyidagilar hosil bo'ladi:

```
/path/to/docker/
├── docker.mp4                 ← manba
├── docker.wav                 ← 1-bosqich (16 kHz mono)
├── docker.srt                 ← 2-bosqich (inglizcha)
├── docker-uz.srt              ← 3-bosqich (o'zbekcha, qo'lda)
├── normalize.json             ← atamalar ro'yxati (ixtiyoriy, o'zingiz yaratasiz)
├── docker-uz-normalized.srt   ← 4-bosqich (TTS uchun tayyorlangan)
├── audios/                    ← 5-bosqich
│   ├── 00-00-01-500.wav
│   └── 00-00-04-200.wav
├── docker-background.wav      ← 6-bosqich (nutqsiz fon)
├── docker-background.mp4      ← 7-bosqich (ovozi almashtirilgan video)
└── docker-uz.mp4              ← 8-bosqich (NATIJA)
```

---

## 5. Sozlamalar

Kodga tegmasdan, environment o'zgaruvchilari orqali:

### 2-bosqich (whisper)

| O'zgaruvchi | Default | Izoh |
|---|---|---|
| `WHISPER_MODEL` | `large-v3` | `large-v3-turbo` — ~4x tez |
| `WHISPER_DEVICE` | `cpu` / `cuda` | `mps` ni sinab ko'rish mumkin |
| `WHISPER_DOWNLOAD_ROOT` | `~/.cache/whisper` | model saqlanadigan papka |

### 5-bosqich (Navoiy TTS)

| O'zgaruvchi | Default | Izoh |
|---|---|---|
| `NAVOIY_REFERENCE` | `navoiy-tts/demo/xurmo.wav` | qaysi ovozda gapirilishi |
| `NAVOIY_EMOTION` | `calm` | hissiyot |
| `NAVOIY_SPEED` | `1.0` | nutq tezligi |
| `NAVOIY_SEED` | `1986` | tasodifiylik urug'i |

Mavjud hissiyotlar: `calm`, `happy`, `excited`, `sad`, `angry`, `nervous`, `scared`,
`surprised`, `whispers`, `warm`, `gentle`, `tired`, `sighs`, `sarcastic`

```bash
.venv/bin/python navoiy-tts/inference.py --list-emotions
```

Mavjud ovoz namunalari: `navoiy-tts/demo/` ichida — `xurmo.wav`, `calm_intro.wav`,
`warm_agent.wav`, `happy.wav`, `sad.wav`, `angry.wav`, `surprised.wav`, `long_form.wav`

### 6-bosqich (demucs)

| O'zgaruvchi | Default | Izoh |
|---|---|---|
| `DEMUCS_MODEL` | `htdemucs` | ajratish modeli |
| `DEMUCS_DEVICE` | `cpu` / `cuda` | Apple Silicon uchun `mps` |

### Kod ichidagi konstantalar

| Fayl | Konstanta | Default | Izoh |
|---|---|---|---|
| `step2_generate_srt.py` | `CONDITION_ON_PREVIOUS_TEXT` | `False` | `True` — kontekst yaxshi, lekin takrorlanish xavfi bor |
| `step5_generate_audios.py` | `FIT_TO_TIMELINE` | `True` | audioni o'z oralig'iga sig'dirish |
| `step5_generate_audios.py` | `MAX_TEMPO` | `1.5` | maksimal tezlashtirish |
| `step8_merge_audios.py` | `ORIGINAL_VOLUME` | `1.0` | fon musiqasining balandligi |

---

## 6. Tez-tez uchraydigan savollar

**Jarayon uzilib qoldi, boshidan boshlash kerakmi?**
Yo'q. Har bir bosqich tayyor natijani qayta hisoblamaydi — `main.py` ni qaytadan ishga tushiring.

**O'zbekcha ovoz yoqmadi, boshqasini sinab ko'rmoqchiman.**

```bash
rm -rf /path/to/docker/audios
NAVOIY_REFERENCE=navoiy-tts/demo/warm_agent.wav .venv/bin/python step5_generate_audios.py
```

**Fon musiqasi o'zbekcha nutqni bosib ketyapti.**
`step8_merge_audios.py` da `ORIGINAL_VOLUME` ni `0.6` ga tushiring va 8-bosqichni qayta ishga
tushiring (u tez ishlaydi — video qayta kodlanmaydi).

**O'zbekcha nutq keyingi jumla ustiga chiqib ketyapti.**
O'zbekcha matn inglizchadan uzunroq bo'ladi. `step5_generate_audios.py` da `MAX_TEMPO` ni `1.8`
ga ko'taring yoki `NAVOIY_SPEED=1.15` bilan generatsiya qiling.

**`ModuleNotFoundError: No module named 'pkg_resources'`**

```bash
.venv/bin/pip install "setuptools<81"
```
