# Video tarjimon: ingliz → o'zbek dublyaj

Ingliz tilidagi videoni **o'zbek tilida gapiriladigan** videoga aylantiradigan loyiha. Videodan nutq ajratib
olinadi, matnga o'giriladi, o'zbekchaga tarjima qilinadi, sun'iy ovoz bilan o'qib beriladi va o'sha audio asl
videoning tasviri ustiga vaqt bo'yicha aniq joylashtiriladi.

Natijada asl video xuddi o'sha holida qoladi — faqat ovoz o'zbekcha bo'ladi.

```
docker9.mp4  →  docker9-result.mp4
(inglizcha)      (o'zbekcha nutq)
```

## Qo'llanmalar

Ish tartibi video turiga qarab farq qiladi. Boshidan oxirigacha bo'lgan jarayon shu ikki faylda:

| Qo'llanma | Kimga | Farqi |
|---|---|---|
| **[readme/COURSE.md](readme/COURSE.md)** | kurs, ma'ruza, skrinkast | fon ovozi butunlay tashlanadi; atamalar lug'ati muhim |
| **[readme/MOVIE.md](readme/MOVIE.md)** | kino, film, serial | fon musiqasi va effektlar saqlanadi (demucs) |

Quyida esa loyihaning umumiy tuzilishi: qaysi fayl nima qiladi va nimalarni o'rnatish kerak.

---

## 1. Quvur qanday ishlaydi

7 bosqich. Har birini **mustaqil** ham ishga tushirish mumkin, `modes/` orqali **ketma-ket** ham.

| #  | Fayl                       | Nima qiladi                                                  | Vosita                          |
|----|----------------------------|--------------------------------------------------------------|---------------------------------|
| 1a | `steps/remove_audio.py`    | Videodan audio qismini butunlay olib tashlaydi               | ffmpeg                          |
| 1b | `steps/remove_vocals.py`   | Videodan faqat odam nutqini olib tashlaydi, fonni qoldiradi  | demucs + ffmpeg                 |
| 2  | `steps/extract_audio.py`   | Asl videodan audio ajratib oladi (16 kHz mono)               | ffmpeg                          |
| 3  | `steps/generate_srt.py`    | Audiodan inglizcha `.srt` yasaydi                            | openai-whisper `large-v3-turbo` |
| 4  | `steps/translate_srt.py`   | `.srt` ni o'zbekchaga tarjima qiladi                         | Claude Code headless (opus 5)   |
| 5  | `steps/normalize_srt.py`   | Atamalarni almashtiradi, sonlar/sanalarni so'zga aylantiradi | terms.json + uztts              |
| 6  | `steps/generate_audios.py` | Har bir subtitr uchun audio generatsiya qiladi               | Navoiy TTS (CosyVoice2)         |
| 7  | `steps/merge_audios.py`    | O'zbekcha audiolarni timestamp bo'yicha videoga qo'yadi      | ffmpeg                          |

1-bosqich **video turiga qarab** tanlanadi: kurs → `1a`, kino → `1b`. Qolgan bosqichlar ikkalasida bir xil.

> **Diqqat:** 2-bosqich transkripsiya uchun **asl** videodan audio oladi (inglizcha nutq faqat o'sha yerda),
> 7-bosqich esa 1-bosqichda tayyorlangan videoni ishlatadi.

Bitta video uchun hosil bo'ladigan fayllar:

```
docker9.mp4                 ← manba
docker9-no-audio.mp4        ← 1a  (kurs)      | docker9-removed-vocal.mp4  ← 1b (kino)
docker9.wav                 ← 2   16 kHz mono
docker9.srt                 ← 3   inglizcha transkripsiya
docker9-uz.srt              ← 4   o'zbekcha tarjima
docker9-uz-normalized.srt   ← 5   TTS uchun tayyorlangan matn
audios/00-00-01-500.wav …   ← 6   har bir subtitr uchun audio
docker9-result.mp4          ← 7   NATIJA
```

---

## 2. Papkalar va fayllar

```
steps/          Quvurning alohida bosqichlari — har biri bitta ish qiladi
├── remove_audio.py       videodan audio oqimini tashlaydi -> <nom>-no-audio.mp4
├── remove_vocals.py      demucs bilan faqat nutqni oladi  -> <nom>-removed-vocal.mp4
├── extract_audio.py      transkripsiya uchun audio ajratadi -> <nom>.wav
├── generate_srt.py       whisper bilan transkripsiya       -> <nom>.srt
├── translate_srt.py      claude -p bilan tarjima           -> <nom>-uz.srt
├── normalize_srt.py      atamalar + sonlarni tayyorlaydi   -> <nom>-uz-normalized.srt
├── generate_audios.py    Navoiy TTS bilan audiolar         -> audios/*.wav
└── merge_audios.py       audiolarni videoga biriktiradi    -> <nom>-result.mp4

modes/          Butun quvurni bitta video uchun boshidan oxirigacha bajaradi
├── course.py             kurs videolari uchun (1a bosqich bilan)
└── movie.py              kinolar uchun (1b bosqich bilan)

pipelines/      Bir nechta bosqichni birlashtirgan qisqartirilgan quvurlar
└── prepare.py            1-3 bosqichlar: ovozsiz video + .wav + inglizcha .srt

batches/        Bir nechta video uchun quvurlarni ketma-ket bajaradi
├── prepare_batch.py       prepare.py ni papkadagi hamma video uchun
├── translate_batch.py     4-bosqichni (tarjima) hamma .srt uchun
└── normalize_srt_batch.py 5-bosqichni (normalize) hamma tarjima uchun

utils/          Umumiy yordamchilar
├── common.py             savollar (ask_path, ask_yes_no), ffmpeg chaqirish, vaqt formati
├── srt.py                .srt ni o'qish/yozish (Cue, parse_srt, write_srt)
├── locate_videos.py      yuklab olingan videolarni assets/ ga tartiblab joylashtiradi
├── collect_terms.py      terms.json uchun atama shakllarini matndan yig'ib beradi
└── fill_terms.py         kurs terms.json dagi bo'sh o'qilishlarni asosiy lug'atdan to'ldiradi

readme/         Video turiga qarab qo'llanmalar (COURSE.md, MOVIE.md)
assets/         Videolar va ular yonidagi barcha oraliq fayllar
navoiy-tts/     O'zbek TTS modeli (checkpoint + uztts matn normalizatsiyasi)
CosyVoice/      TTS runtime (navoiy-tts shunga tayanadi)
terms.example.json  Atamalar lug'ati namunasi
```

Barcha komandalar **loyiha ildizidan** ishga tushiriladi:

```bash
.venv/bin/python steps/remove_audio.py
```

Modul ko'rinishida ham ishlaydi: `.venv/bin/python -m steps.remove_audio`

---

## 3. O'rnatish

### 3.1. Tizim talablari

| Nima | Nima uchun | O'rnatish |
|---|---|---|
| **ffmpeg** + **ffprobe** | 1, 2, 7-bosqichlar | `brew install ffmpeg` |
| **Python 3.12** | loyihaning `.venv` si | — |
| **claude CLI** | 4-bosqich (tarjima) | `npm install -g @anthropic-ai/claude-code` |
| **demucs** | faqat kino rejimi (1b) | `.venv/bin/pip install demucs` |

`claude` CLI uchun **Claude obunasi** kerak. O'rnatgandan keyin bir marta terminalda `claude` deb ishga
tushiring va brauzer orqali tizimga kiring — keyin headless rejim shu sessiyadan foydalanadi.

### 3.2. Python kutubxonalari

```bash
.venv/bin/pip install -U openai-whisper "setuptools<81"
```

> `large-v3-turbo` uchun `openai-whisper` ning kamida **20240930** versiyasi kerak (loyihada `20250625`).
> Eski versiyada `RuntimeError: Model large-v3-turbo not found` chiqadi.

> `setuptools<81` majburiy: yangi versiyalarda `pkg_resources` olib tashlangan, CosyVoice ishlatadigan
> `lightning` esa unga tayanadi.

### 3.3. Modellar

**Avtomatik yuklab olinadi** (birinchi ishga tushirishda):

- **whisper `large-v3-turbo`** — ~1.6 GB, `~/.cache/whisper` ga
- **demucs `htdemucs`** — ~300 MB (faqat kino rejimida)

**Qo'lda yuklab olinadi:**

- **CosyVoice2-0.5B** — ~4.5 GB
- **Navoiy checkpoint** — `navoiy-tts/emotion_600h_joint.pt`

CosyVoice repozitoriyasi. `--recursive` **majburiy** — `third_party/Matcha-TTS` submodul sifatida ulangan:

```bash
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
```

Model (ModelScope orqali — CosyVoice hujjatida tavsiya etilgan yo'l):

```bash
.venv/bin/python -c "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice2-0.5B', local_dir='CosyVoice/pretrained_models/CosyVoice2-0.5B')"
```

ModelScope sekin ishlasa, HuggingFace orqali:

```bash
.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('FunAudioLLM/CosyVoice2-0.5B', local_dir='CosyVoice/pretrained_models/CosyVoice2-0.5B')"
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

## 4. Birinchi ishga tushirish

Hammasi o'rnatilgach, bitta video bilan sinab ko'ring:

```bash
.venv/bin/python modes/course.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
```

Dastur 7 bosqichni ketma-ket bajaradi va oxirida `<nom>-result.mp4` beradi. Birinchi ishga tushirishda
modellar yuklab olinadi, shuning uchun sekinroq bo'ladi.

Ko'p video bilan ishlash, atamalar lug'ati va boshqa tafsilotlar uchun:
**[readme/COURSE.md](readme/COURSE.md)** yoki **[readme/MOVIE.md](readme/MOVIE.md)**.

---

## 5. Sozlamalar

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

Mavjud hissiyotlar: `calm`, `happy`, `excited`, `sad`, `angry`, `nervous`, `scared`, `surprised`,
`whispers`, `warm`, `gentle`, `tired`, `sighs`, `sarcastic`

```bash
.venv/bin/python navoiy-tts/inference.py --list-emotions
```

Ovoz namunalari `navoiy-tts/demo/` ichida: `xurmo.wav`, `calm_intro.wav`, `warm_agent.wav`, `happy.wav`,
`sad.wav`, `angry.wav`, `surprised.wav`, `long_form.wav`

### 1b-bosqich (demucs, faqat kino)

| O'zgaruvchi     | Default        | Izoh                      |
|-----------------|----------------|---------------------------|
| `DEMUCS_MODEL`  | `htdemucs`     | nutqni ajratish modeli    |
| `DEMUCS_DEVICE` | `cpu` / `cuda` | Apple Silicon uchun `mps` |

### Kod ichidagi konstantalar

| Fayl                       | Konstanta                    | Default          | Izoh                                       |
|----------------------------|------------------------------|------------------|--------------------------------------------|
| `steps/remove_audio.py`    | `OUTPUT_SUFFIX`              | `-no-audio`      | ovozsiz video nomiga qo'shimcha            |
| `steps/remove_vocals.py`   | `OUTPUT_SUFFIX`              | `-removed-vocal` | nutqsiz video nomiga qo'shimcha            |
| `steps/generate_srt.py`    | `CONDITION_ON_PREVIOUS_TEXT` | `False`          | `True` — kontekst yaxshi, takror xavfi bor |
| `steps/generate_audios.py` | `FIT_TO_TIMELINE`            | `True`           | audioni o'z oralig'iga sig'dirish          |
| `steps/generate_audios.py` | `MAX_TEMPO`                  | `1.5`            | maksimal tezlashtirish                     |
| `steps/merge_audios.py`    | `ORIGINAL_VOLUME`            | `1.0`            | videoda audio bo'lsa, uning balandligi     |
| `steps/merge_audios.py`    | `OUTPUT_SUFFIX`              | `-result`        | yakuniy video nomiga qo'shimcha            |

---

## 6. Tez-tez uchraydigan savollar

**Jarayon uzilib qoldi, boshidan boshlash kerakmi?**
Yo'q. Har bir bosqich tayyor natijani qayta hisoblamaydi — qaytadan ishga tushiring.

**TTS inglizcha atamani noto'g'ri o'qiyapti.**
Uni `terms.json` ga fonetik ko'rinishda qo'shing (`"docker": "do'ker"`). Model ichiga yangi so'z "o'rgatib"
bo'lmaydi — CosyVoice2 da leksikon qatlami yo'q, shuning uchun yagona yo'l shu.

**O'zbekcha nutq keyingi jumla ustiga chiqib ketyapti.**
O'zbekcha matn inglizchadan uzunroq bo'ladi. `steps/generate_audios.py` da `MAX_TEMPO` ni `1.8` ga ko'taring
yoki `NAVOIY_SPEED=1.15` bilan generatsiya qiling.

**Videoning fon musiqasi kerak.**
Kino rejimini oling: [readme/MOVIE.md](readme/MOVIE.md).

**`ModuleNotFoundError: No module named 'pkg_resources'`**

```bash
.venv/bin/pip install "setuptools<81"
```
