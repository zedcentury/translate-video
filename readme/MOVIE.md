# Kinolarni dublyaj qilish (`modes/movie.py`)

Kino, film, serial kabi videolar uchun. Bunday videolarda fon musiqasi, effektlar va tabiat tovushlari
ahamiyatli, shuning uchun **1-bosqichda audio butunlay tashlanmaydi** — demucs orqali undan faqat odam nutqi
ajratib olinadi, fon esa joyida qoladi va yakuniy videoda o'zbekcha nutq ostida eshitiladi.

> Kurs, ma'ruza, skrinkast uchun [COURSE.md](COURSE.md) ga qarang — u yerda audio butunlay tashlanadi.

O'rnatish va umumiy struktura — loyiha ildizidagi [README.md](../README.md) da.

---

## Qo'shimcha talab: demucs

Bu rejim demucs'ga tayanadi (model birinchi ishlatilganda ~300 MB yuklab olinadi):

```bash
.venv/bin/pip install demucs
```

1-bosqich **sekin**: CPU da taxminan real vaqtda ishlaydi (1 soatlik kino ≈ 1 soat). Apple Silicon'da
tezlashtirish uchun:

```bash
DEMUCS_DEVICE=mps .venv/bin/python modes/movie.py
```

---

## Tez yo'l: butun quvurni bir komanda bilan

```bash
.venv/bin/python modes/movie.py
```

```
Video fayl manzilini kiriting (/path/to/movie/movie.mp4): /path/to/movie/movie.mp4
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

> **Diqqat:** 2-bosqich transkripsiya uchun **asl** videodan audio oladi (inglizcha nutq faqat o'sha yerda),
> 7-bosqich esa 1-bosqichda tayyorlangan nutqsiz videoni ishlatadi.

Rejim ishga tushgach dastur o'zi ishlaydi va faqat quyidagi joylarda to'xtaydi:

1. `-removed-vocal` video allaqachon mavjud bo'lsa — qayta yasashni so'raydi (Enter = yo'q)
2. `.srt` allaqachon mavjud bo'lsa — qayta generatsiya qilishni so'raydi (Enter = yo'q)
3. **4-bosqich** — tarjima allaqachon mavjud bo'lsa, qayta tarjima qilishni so'raydi (Enter = yo'q)
4. **5-bosqich** — atamalar JSON faylini so'raydi (kerak bo'lmasa Enter)

---

## Kurs rejimidan farqi

Faqat **ikki joyda**:

| | `course.py` | `movie.py` |
|---|---|---|
| 1-bosqich | `remove_audio.py` — audio oqimi tashlanadi | `remove_vocals.py` — demucs faqat nutqni oladi |
| oraliq video | `movie-no-audio.mp4` (ovozsiz) | `movie-removed-vocal.mp4` (fon ovozi bilan) |
| 7-bosqich | videoda audio yo'q — faqat o'zbekcha nutq | videoda fon bor — u ham aralashmaga tushadi |

Qolgan bosqichlar (2-6) mutlaqo bir xil.

---

## Bosqichma-bosqich: `/path/to/movie/movie.mp4` misolida

Har bir bosqichni alohida ham ishga tushirish mumkin. Barcha savollarda kvadrat qavs ichidagi qiymat —
default; **Enter** bosish kifoya.

### 1-bosqich — videodan odam nutqini olib tashlash

```bash
.venv/bin/python steps/remove_vocals.py
```

```
Video fayl manzilini kiriting (/path/to/movie/movie.mp4): /path/to/movie/movie.mp4
Nutqsiz video qayerga saqlansin [/path/to/movie/movie-removed-vocal.mp4]: ⏎
```

Ichkarida uch amal bajariladi:

1. videodan 44.1 kHz stereo audio ajratiladi (demucs shu formatni kutadi);
2. `demucs --two-stems=vocals` nutqni fondan ajratadi;
3. nutqsiz fon audiosi videoga yagona audio oqim sifatida biriktiriladi.

**Natija:** `/path/to/movie/movie-removed-vocal.mp4` — tasvir o'zgarmaydi (`-c:v copy`), ovozda inglizcha nutq
qolmaydi, musiqa va effektlar esa joyida. Oraliq `.wav` fayllar avtomatik o'chiriladi.

Fon audiosini alohida saqlab qolmoqchi bo'lsangiz, funksiyani koddan chaqirib `background_audio` argumentini
bering.

| O'zgaruvchi     | Default        | Izoh                      |
|-----------------|----------------|---------------------------|
| `DEMUCS_MODEL`  | `htdemucs`     | nutqni ajratish modeli    |
| `DEMUCS_DEVICE` | `cpu` / `cuda` | Apple Silicon uchun `mps` |

---

### 2-bosqich — videodan audio ajratish

```bash
.venv/bin/python steps/extract_audio.py
```

```
Video fayl manzilini kiriting (/path/to/movie/movie.mp4): /path/to/movie/movie.mp4
Audio fayl qayerga saqlansin [/path/to/movie/movie.wav]: ⏎
```

**Natija:** `/path/to/movie/movie.wav` (16 kHz mono — whisper uchun optimal)

Bu yerga **asl** video beriladi, nutqsiz nusxa emas — transkripsiya uchun aynan nutq kerak.

---

### 3-bosqich — transkripsiya (inglizcha `.srt`)

```bash
.venv/bin/python steps/generate_srt.py
```

```
Audio fayl manzilini kiriting (/path/to/movie/movie.wav): /path/to/movie/movie.wav
Transkripsiya .srt fayli qayerga saqlansin [/path/to/movie/movie.srt]: ⏎
Audiodagi nutq tili (auto — o'zi aniqlaydi) [en]: ⏎
```

**Natija:** `/path/to/movie/movie.srt`

Kinoda fon musiqasi baland bo'lsa yoki bir necha odam gaplashsa, transkripsiya sifati pasayadi. Shunday
holatda to'liq modelni sinab ko'ring:

```bash
WHISPER_MODEL=large-v3 .venv/bin/python steps/generate_srt.py
```

---

### 4-bosqich — tarjima (Claude Code headless)

```bash
.venv/bin/python steps/translate_srt.py
```

```
Tarjima qilinadigan .srt fayl manzilini kiriting: /path/to/movie/movie.srt
Tarjima qilingan .srt fayl qayerga saqlansin [/path/to/movie/movie-uz.srt]: ⏎
  Yo'nalish: en -> uz | 640 ta subtitr
  Model: claude-opus-5 (effort=high) — bu biroz vaqt oladi...
  410 ta subtitr yozildi (4 daqiqa 3 soniya, $1.8420).
```

**Natija:** `/path/to/movie/movie-uz.srt`

Butun `.srt` matni `claude -p` ga prompt sifatida beriladi va model tayyor `.srt` qaytaradi. Prompt bloklarni
birlashtirishga ruxsat bergani uchun natijada bloklar soni kamayishi normal.

Kino uzun bo'lgani uchun bitta chaqiruv uzoq davom etadi — kerak bo'lsa vaqt chegarasini oshiring:

```bash
CLAUDE_TIMEOUT=7200 .venv/bin/python steps/translate_srt.py
```

| O'zgaruvchi      | Default          | Izoh                        |
|------------------|------------------|-----------------------------|
| `CLAUDE_MODEL`   | `claude-opus-5`  | tarjima qiladigan model     |
| `CLAUDE_EFFORT`  | `high`           | effort darajasi             |
| `CLAUDE_TIMEOUT` | `3600`           | bitta chaqiruv uchun sekund |

---

### 5-bosqich — matnni TTS uchun normalize qilish

```bash
.venv/bin/python steps/normalize_srt.py
```

```
Tarjima qilingan .srt fayl manzilini kiriting (/path/to/movie/movie-uz.srt): /path/to/movie/movie-uz.srt
Normalize qilingan .srt qayerga saqlansin [/path/to/movie/movie-uz-normalized.srt]: ⏎
Atamalar JSON fayli manzilini kiriting (/path/to/movie/normalize.json) (o'tkazib yuborish uchun Enter): ⏎
```

**Natija:** `/path/to/movie/movie-uz-normalized.srt`

Kinoda texnik atamalar kam bo'ladi, shuning uchun atamalar faylini ko'pincha bo'sh qoldirsa bo'ladi (Enter) —
u holda faqat sonlar, sanalar va vaqt so'zga aylantiriladi:

```
Bugun 16.07.2026, soat 14:30 da uchrashamiz.
→ Bugun o'n olti iyul ikki ming yigirma olti, soat o'n to'rt o'ttiz da uchrashamiz.
```

Ismlar va joy nomlari noto'g'ri o'qilsa, ularni JSON ga qo'shing:

```json
{
  "Michael": "Maykl",
  "New York": "Nyu York"
}
```

Atama **faqat ikki tomonida ham bo'shliq** bo'lganda almashtiriladi (matn boshi va oxiri ham bo'shliq deb
qaraladi). Ya'ni `Michael.` yoki `Michael'ga` shakllarini ham almashtirmoqchi bo'lsangiz, ularni alohida kalit
qilib qo'shing.

---

### 6-bosqich — o'zbekcha audiolar (TTS)

```bash
.venv/bin/python steps/generate_audios.py
```

```
Normalize qilingan .srt fayl manzilini kiriting (/path/to/movie/movie-uz-normalized.srt): /path/to/movie/movie-uz-normalized.srt
Audiolar qaysi papkaga saqlansin [/path/to/movie/audios]: ⏎
```

**Natija:** `/path/to/movie/audios/00-00-01-500.wav`, `00-00-04-200.wav`, …

Fayl nomi — subtitrning **boshlanish vaqti**. 7-bosqich audioni videoga aynan shu nom bo'yicha joylashtiradi,
shuning uchun fayllarni qayta nomlamang.

- Model **bir marta** yuklanadi, barcha segmentlar shu jarayonda generatsiya qilinadi
- Papkada tayyor fayl bo'lsa, qayta generatsiya qilinmaydi (uzilgan jarayonni davom ettirish mumkin).
  Butunlay yangilash uchun: `rm -rf /path/to/movie/audios`
- Audio o'z oralig'iga sig'masa, avtomatik tezlashtiriladi (maksimum 1.5x)

Kinoda hissiyot muhim. Mavjud hissiyotlar: `calm`, `happy`, `excited`, `sad`, `angry`, `nervous`, `scared`,
`surprised`, `whispers`, `warm`, `gentle`, `tired`, `sighs`, `sarcastic`

```bash
NAVOIY_EMOTION=warm NAVOIY_REFERENCE=navoiy-tts/demo/long_form.wav \
  .venv/bin/python steps/generate_audios.py
```

> Hissiyot butun fayl uchun bitta bo'ladi — sahna-sahna o'zgartirish hozircha qo'llab-quvvatlanmaydi.

---

### 7-bosqich — o'zbekcha audiolarni biriktirish

```bash
.venv/bin/python steps/merge_audios.py
```

```
Ovozsiz video fayl manzilini kiriting (/path/to/movie/movie-removed-vocal.mp4): /path/to/movie/movie-removed-vocal.mp4
Audiolar joylashgan papka manzilini kiriting [/path/to/movie/audios]: ⏎
```

> **Diqqat:** bu yerda asl `movie.mp4` emas, 1-bosqichdan chiqqan `movie-removed-vocal.mp4` berilishi kerak.
> Aks holda inglizcha nutq qaytib qo'shiladi.

Videoda fon ovozi borligi uchun ekranda shunday chiqadi:

```
  Videoning o'z ovozi ham aralashmaga qo'shiladi (volume=1.0).
```

**Natija:** `/path/to/movie/movie-result.mp4` — fon musiqasi va o'zbekcha nutq aralashgan tayyor video

**Fon baland tuyulsa**, [steps/merge_audios.py](../steps/merge_audios.py) dagi `ORIGINAL_VOLUME` ni `0.3`–`0.6`
ga tushiring va faqat shu bosqichni qayta ishga tushiring — u tez ishlaydi, video qayta kodlanmaydi.

---

## Fayllar xaritasi

`/path/to/movie/movie.mp4` uchun quvur oxirida:

```
/path/to/movie/
├── movie.mp4                  ← manba
├── movie-removed-vocal.mp4    ← 1-bosqich (nutqsiz, fon ovozi bilan)
├── movie.wav                  ← 2-bosqich (16 kHz mono)
├── movie.srt                  ← 3-bosqich (inglizcha)
├── movie-uz.srt               ← 4-bosqich (o'zbekcha, claude -p)
├── normalize.json             ← ismlar/atamalar ro'yxati (ixtiyoriy)
├── movie-uz-normalized.srt    ← 5-bosqich (TTS uchun tayyorlangan)
├── audios/                    ← 6-bosqich
│   ├── 00-00-01-500.wav
│   └── 00-00-04-200.wav
└── movie-result.mp4           ← 7-bosqich (NATIJA)
```

---

## Kinoga oid maslahatlar

**1-bosqich juda sekin.** Demucs kinoning butun uzunligini qayta ishlaydi. `DEMUCS_DEVICE=mps` ni sinab
ko'ring; ishlamasa, tunda qoldiring — natija saqlanadi va keyingi ishga tushirishda qayta hisoblanmaydi.

**Fon ovozi nutqni bosib ketyapti.** `ORIGINAL_VOLUME` ni pasaytiring (7-bosqich).

**Demucs fonni ham buzib qo'ydi.** Ba'zi yozuvlarda nutq va musiqa qattiq aralashgan bo'ladi. Boshqa model
sinab ko'ring: `DEMUCS_MODEL=htdemucs_ft` (sekinroq, sifatliroq).

**Original ovoz umuman kerak emas.** Unda kino rejimi emas, kurs rejimi kerak: [COURSE.md](COURSE.md).

**Jarayon uzilib qoldi.** Qaytadan ishga tushiring — har bir bosqich tayyor natijani qayta hisoblamaydi.
