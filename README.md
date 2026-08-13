# Video tarjimon: ingliz → o'zbek dublyaj

Ingliz tilidagi videoni o'zbek tilida gapiriladigan variantga o'tkazish uchun mo'ljallangan 7 bosqichli quvur
(pipeline). Har bir bosqich alohida faylda va uni **mustaqil ravishda** ham,
`main.py` orqali **ketma-ket** ham ishga tushirish mumkin.

| # | Fayl                       | Nima qiladi                                                  | Vosita                    |
|---|----------------------------|--------------------------------------------------------------|---------------------------|
| 1 | `step1_remove_audio.py`    | Videodan audio qismini butunlay olib tashlaydi               | ffmpeg                    |
| 2 | `step2_extract_audio.py`   | Asl videodan audio ajratib oladi                             | ffmpeg                    |
| 3 | `step3_generate_srt.py`    | Audiodan inglizcha `.srt` yasaydi                            | openai-whisper `large-v3-turbo` |
| 4 | `step4_translate_srt.py`   | `.srt` ni o'zbekchaga tarjima qiladi                         | **qo'lda** (LLM)          |
| 5 | `step5_normalize_srt.py`   | Sonlar/sanalarni so'zga aylantiradi, atamalarni almashtiradi | uztts                     |
| 6 | `step6_generate_audios.py` | Har bir subtitr uchun audio generatsiya qiladi               | Navoiy TTS (CosyVoice2)   |
| 7 | `step7_merge_audios.py`    | O'zbekcha audiolarni timestamp bo'yicha qo'yadi              | ffmpeg                    |

> **Diqqat:** 2-bosqich transkripsiya uchun **asl** videodan audio oladi (nutq faqat o'sha yerda),
> 7-bosqich esa 1-bosqichda tayyorlangan **ovozsiz** videoni ishlatadi.

> Kurslar uchun orqa fondagi musiqa/effektlar kerak emas, shuning uchun 1-bosqich nutqni fondan
> ajratmaydi (demucs) — audio oqimi butunlay tashlab yuboriladi.

---

## 1. O'rnatish

### Talablar

- **ffmpeg** va **ffprobe** — `brew install ffmpeg`
- **Python 3.12** (loyihadagi `.venv` shu versiyada)
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
2. **4-bosqich** — o'zbekcha tarjimani qo'lda tayyorlashingizni kutadi (pastga qarang)
3. **5-bosqich** — atamalar JSON faylini so'raydi (kerak bo'lmasa Enter)

---

## 2.1. Ko'p video uchun: `mini.py` va `mini_batch.py`

Tarjimadan oldingi tayyorgarlik (1-3 bosqichlar: ovozsiz video + `.wav` + inglizcha `.srt`)
alohida ajratilgan, chunki 4-bosqich qo'lda bajariladi.

**Bitta video uchun** — barcha savollar boshida bir marta so'raladi:

```bash
.venv/bin/python mini.py
```

**Bir nechta video uchun** — bitta komanda bilan ketma-ket:

```bash
.venv/bin/python mini_batch.py
```

```
Path (video papkalari joylashgan ota papka): /path/to/assets/docker
Start (masalan 18 -> docker18 dan boshlanadi) [1]: 18
```

Har bir papka nomidan uning ichidagi fayllar aniqlanadi (`docker9` → `docker9/docker9.mp4`,
`docker9-no-audio.mp4`, `docker9.wav`, `docker9.srt`, til `en`). Papkalar nomidagi **raqam**
bo'yicha tartiblanadi (`docker2` → `docker10` → `docker100`), shuning uchun `Start` aynan shu
raqamga qaraydi. Uch natijasi ham tayyor papka o'tkazib yuboriladi, bitta video xato bersa quvur
to'xtamaydi — oxirida hisobot chiqadi.

---

## 3. Bosqichma-bosqich: `/path/to/docker/docker.mp4` misolida

Quyida har bir faylni alohida ishga tushirish tartibi. Barcha savollarda kvadrat qavs ichidagi qiymat — default;
**Enter** bosish kifoya.

### 1-bosqich — videodan audioni olib tashlash

```bash
.venv/bin/python step1_remove_audio.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
Ovozsiz video qayerga saqlansin [/path/to/docker/docker-no-audio.mp4]: ⏎
```

**Natija:** `/path/to/docker/docker-no-audio.mp4` — tasvir o'zgarmaydi (`-c:v copy`), audio oqimi esa
umuman yo'q. Bir necha soniyada tugaydi.

---

### 2-bosqich — videodan audio ajratish

```bash
.venv/bin/python step2_extract_audio.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
Audio fayl qayerga saqlansin [/path/to/docker/docker.wav]: ⏎
```

**Natija:** `/path/to/docker/docker.wav` (16 kHz mono — whisper uchun optimal)

---

### 3-bosqich — transkripsiya (inglizcha `.srt`)

```bash
.venv/bin/python step3_generate_srt.py
```

```
Audio fayl manzilini kiriting (/path/to/docker/docker.wav): /path/to/docker/docker.wav
Transkripsiya .srt fayli qayerga saqlansin [/path/to/docker/docker.srt]: ⏎
Audiodagi nutq tili (auto — o'zi aniqlaydi) [en]: ⏎
```

**Natija:** `/path/to/docker/docker.srt`

Til savolida Enter bosilsa `en` olinadi. Boshqa til uchun `ru`, `uz` kabi kod kiriting;
`auto` deb yozsangiz, whisper tilni o'zi aniqlaydi.

Default model — `large-v3-turbo`: `large-v3` ning qisqartirilgan dekoderli varianti, bir necha
barobar tez ishlaydi va transkripsiya sifati deyarli o'zgarmaydi. Aniqroq natija kerak bo'lsa
(masalan sifati past, shovqinli yozuv), to'liq modelga qaytish mumkin:

```bash
WHISPER_MODEL=large-v3 .venv/bin/python step3_generate_srt.py
```

---

### 4-bosqich — tarjima (QO'LDA)

```bash
.venv/bin/python step4_translate_srt.py
```

```
Tarjima qilinadigan .srt fayl manzilini kiriting: /path/to/docker/docker.srt
Tarjima qilingan .srt fayl qayerga saqlansin [/path/to/docker/docker-uz.srt]: ⏎
  Tarjima hozircha qo'lda bajariladi. docker-uz.srt tayyormi? [ha/yo'q]:
```

Bu paytda `/path/to/docker/docker.srt` faylini Claude / ChatGPT / Gemini ga yuklab, quyidagi prompt bilan tarjima
qildiring, natijani `/path/to/docker/docker-uz.srt` nomi bilan saqlang, so'ng `ha` deb javob bering:

```text
Yuklangan .srt faylni o'zbek tiliga (lotin) tarjima qil. Timestamp'lar o'zgarmasin, format saqlansin. Gap yoki atama ikki blokka bo'linib qolgan joylarda bloklarni birlashtirishga ruxsat — birlashgan blok birinchi bo'lakning boshi va oxirgi bo'lakning oxiri vaqtini olsin, keyin qayta raqamla. Texnik atamalar va ismlar tarjima qilinmasdan, asl inglizcha yozuvida qolsin. Uslub — jonli, o'qituvchi so'zlayotgandek. Transkripsiya xatolarini to'g'irlab tarjima qil. Natijada IKKITA fayl ber:

1. Tarjima qilingan .srt fayl.
2. .json fayl — tarjimada inglizcha holida qolgan barcha so'zlar lug'ati:
   * Kalit (key) — srt faylda uchragan aynan o'sha yozuv.
   * Qiymat (value) — o'sha so'zning o'zbekcha o'qilishi, o'zbek lotin harflarida (inglizcha talaffuzga asoslanib).
   * Har bir yozuv shakli alohida kalit bo'lsin: "Docker" va "docker" — ikki xil yozuv.
   * Takrorlanmasin, har bir so'z bir marta. Alifbo tartibida joylashtir.
   * Faqat toza JSON — izohsiz, markdown belgilarsiz, tekis (nested emas) tuzilishda. Namuna: { "container": "kanteynr", "deploy": "deplo'y", "Docker": "Do'ker", "docker": "do'ker", "Kubernetes": "Kubernits", "kubernetes": "kubernits", "Maximilian": "Maksimillian", "Schwarzmuller": "Shvarzmyuller" }
```

**Natija:** `/path/to/docker/docker-uz.srt`

---

### 5-bosqich — matnni TTS uchun normalize qilish

```bash
.venv/bin/python step5_normalize_srt.py
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
.venv/bin/python step6_generate_audios.py
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
.venv/bin/python step7_merge_audios.py
```

```
Ovozsiz video fayl manzilini kiriting (/path/to/docker/docker-no-audio.mp4): /path/to/docker/docker-no-audio.mp4
Audiolar joylashgan papka manzilini kiriting [/path/to/docker/audios]: ⏎
```

> **Diqqat:** bu yerda asl `video.mp4` emas, 1-bosqichdan chiqqan `video-no-audio.mp4`
> berilishi kerak. Aks holda inglizcha nutq qaytib qo'shiladi.

**Natija:** `/path/to/docker/docker-no-audio-uz.mp4` — tayyor dublyaj qilingan video

> `main.py` orqali ishlatilganda natija `/path/to/docker/docker-uz.mp4` deb nomlanadi.

---

## 4. Fayllar xaritasi

`/path/to/docker/docker.mp4` uchun quvur oxirida quyidagilar hosil bo'ladi:

```
/path/to/docker/
├── docker.mp4                 ← manba
├── docker-no-audio.mp4        ← 1-bosqich (ovozsiz video)
├── docker.wav                 ← 2-bosqich (16 kHz mono)
├── docker.srt                 ← 3-bosqich (inglizcha)
├── docker-uz.srt              ← 4-bosqich (o'zbekcha, qo'lda)
├── normalize.json             ← atamalar ro'yxati (ixtiyoriy, o'zingiz yaratasiz)
├── docker-uz-normalized.srt   ← 5-bosqich (TTS uchun tayyorlangan)
├── audios/                    ← 6-bosqich
│   ├── 00-00-01-500.wav
│   └── 00-00-04-200.wav
└── docker-uz.mp4              ← 7-bosqich (NATIJA)
```

---

## 5. Sozlamalar

Kodga tegmasdan, environment o'zgaruvchilari orqali:

### 3-bosqich (whisper)

| O'zgaruvchi             | Default            | Izoh                          |
|-------------------------|--------------------|-------------------------------|
| `WHISPER_MODEL`         | `large-v3-turbo`   | `large-v3` — sekinroq, aniqroq |
| `WHISPER_DEVICE`        | `cpu` / `cuda`     | `mps` ni sinab ko'rish mumkin |
| `WHISPER_DOWNLOAD_ROOT` | `~/.cache/whisper` | model saqlanadigan papka      |

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

### Kod ichidagi konstantalar

| Fayl                       | Konstanta                    | Default      | Izoh                                                    |
|----------------------------|------------------------------|--------------|---------------------------------------------------------|
| `step1_remove_audio.py`    | `OUTPUT_SUFFIX`              | `-no-audio`  | ovozsiz video nomiga qo'shimcha                         |
| `step3_generate_srt.py`    | `CONDITION_ON_PREVIOUS_TEXT` | `False`      | `True` — kontekst yaxshi, lekin takrorlanish xavfi bor  |
| `step6_generate_audios.py` | `FIT_TO_TIMELINE`            | `True`       | audioni o'z oralig'iga sig'dirish                       |
| `step6_generate_audios.py` | `MAX_TEMPO`                  | `1.5`        | maksimal tezlashtirish                                  |
| `step7_merge_audios.py`    | `ORIGINAL_VOLUME`            | `1.0`        | videoda audio bo'lsa, uning balandligi                  |

---

## 6. Tez-tez uchraydigan savollar

**Jarayon uzilib qoldi, boshidan boshlash kerakmi?**
Yo'q. Har bir bosqich tayyor natijani qayta hisoblamaydi — `main.py` ni qaytadan ishga tushiring.

**O'zbekcha ovoz yoqmadi, boshqasini sinab ko'rmoqchiman.**

```bash
rm -rf /path/to/docker/audios
NAVOIY_REFERENCE=navoiy-tts/demo/warm_agent.wav .venv/bin/python step6_generate_audios.py
```

**Videoning fon musiqasi kerak bo'lsa-chi?**
Hozirgi quvur uni saqlamaydi — 1-bosqich audio oqimini butunlay tashlab yuboradi. Fon kerak bo'lsa,
7-bosqichga ovozsiz nusxa o'rniga **asl** videoni bering va `step7_merge_audios.py` dagi
`ORIGINAL_VOLUME` ni `0.3`–`0.6` ga tushiring (lekin unda inglizcha nutq ham eshitiladi).

**O'zbekcha nutq keyingi jumla ustiga chiqib ketyapti.**
O'zbekcha matn inglizchadan uzunroq bo'ladi. `step6_generate_audios.py` da `MAX_TEMPO` ni `1.8`
ga ko'taring yoki `NAVOIY_SPEED=1.15` bilan generatsiya qiling.

**`ModuleNotFoundError: No module named 'pkg_resources'`**

```bash
.venv/bin/pip install "setuptools<81"
```
