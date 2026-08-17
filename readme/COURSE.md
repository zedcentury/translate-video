# Kurs videolarini dublyaj qilish (`modes/course.py`)

Kurs, ma'ruza, skrinkast kabi videolar uchun. Bunday videolarda orqa fondagi musiqa va effektlar odatda kerak
emas, shuning uchun **1-bosqichda audio oqimi butunlay tashlab yuboriladi** va yakuniy videoda faqat o'zbekcha
nutq eshitiladi.

> Kino, film yoki fon musiqasi muhim bo'lgan video uchun [MOVIE.md](MOVIE.md) ga qarang.

O'rnatish va umumiy struktura — loyiha ildizidagi [README.md](../README.md) da.

---

## Tez yo'l: butun quvurni bir komanda bilan

```bash
.venv/bin/python modes/course.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
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

> **Diqqat:** 2-bosqich transkripsiya uchun **asl** videodan audio oladi (inglizcha nutq faqat o'sha yerda),
> 7-bosqich esa 1-bosqichda tayyorlangan ovozsiz videoni ishlatadi.

Rejim ishga tushgach dastur o'zi ishlaydi va faqat quyidagi joylarda to'xtaydi:

1. `.srt` allaqachon mavjud bo'lsa — qayta generatsiya qilishni so'raydi (Enter = yo'q)
2. **4-bosqich** — tarjima allaqachon mavjud bo'lsa, qayta tarjima qilishni so'raydi (Enter = yo'q)
3. **5-bosqich** — atamalar JSON faylini so'raydi (kerak bo'lmasa Enter)

Oxirida umumiy vaqt chiqadi:

```
============================================================
 Tayyor! Natija: /path/to/docker/docker-result.mp4
 Umumiy vaqt: 1 soat 24 daqiqa 7 soniya
============================================================
```

---

## Ko'p video uchun

Kurs odatda o'nlab video'dan iborat bo'ladi. Shuning uchun quvur uch qismga bo'lingan va har biri butun papka
uchun birdan ishlaydi:

```bash
.venv/bin/python batches/prepare_batch.py        # 1-3 bosqichlar (ovozsiz video + .wav + inglizcha .srt)
.venv/bin/python batches/translate_batch.py      # 4-bosqich (tarjima)
.venv/bin/python batches/normalize_srt_batch.py  # 5-bosqich (normalize)
```

Batafsil: [README.md](../README.md) dagi "Ko'p video uchun" bo'limi.

---

## Bosqichma-bosqich: `/path/to/docker/docker.mp4` misolida

Har bir bosqichni alohida ham ishga tushirish mumkin. Barcha savollarda kvadrat qavs ichidagi qiymat —
default; **Enter** bosish kifoya.

### 1-bosqich — videodan audioni olib tashlash

```bash
.venv/bin/python steps/remove_audio.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): /path/to/docker/docker.mp4
Ovozsiz video qayerga saqlansin [/path/to/docker/docker-no-audio.mp4]: ⏎
```

**Natija:** `/path/to/docker/docker-no-audio.mp4` — tasvir o'zgarmaydi (`-c:v copy`), audio oqimi esa umuman
yo'q. Bir necha soniyada tugaydi.

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

Default model — `large-v3-turbo`. Sifati past, shovqinli yozuv uchun to'liq modelga qaytish mumkin:

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

Kurs videolarida texnik atamalar ko'p bo'ladi — prompt ularni **tarjima qilmasdan**, asl inglizcha yozuvida
qoldiradi (`container`, `Docker Compose`, `Node.js`). Ularning o'qilishi 5-bosqichda hal qilinadi.

Har bir chaqiruv pullik, shuning uchun tarjima mavjud bo'lsa qayta tarjima so'raladi (Enter = yo'q).

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
Tarjima qilingan .srt fayl manzilini kiriting (/path/to/docker/docker-uz.srt): /path/to/docker/docker-uz.srt
Normalize qilingan .srt qayerga saqlansin [/path/to/docker/docker-uz-normalized.srt]: ⏎
Atamalar JSON fayli manzilini kiriting (/path/to/docker/normalize.json) (o'tkazib yuborish uchun Enter): /path/to/docker/normalize.json
```

**Natija:** `/path/to/docker/docker-uz-normalized.srt`

Bu bosqich **kurs videolari uchun eng muhimi** — TTS inglizcha atamalarni noto'g'ri o'qiydi. Ikki amal shu
tartibda bajariladi:

**1) Atamalar almashtiriladi** (`normalize.json`):

```json
{
  "docker": "do'ker",
  "kubernetes": "kubernites",
  "container": "konteyner"
}
```

Atama **faqat ikki tomonida ham bo'shliq** bo'lganda almashtiriladi (matn boshi va oxiri ham bo'shliq deb
qaraladi):

| Matn | Natija | Sabab |
|---|---|---|
| `docker run` | ✅ `do'ker run` | ikki tomonida bo'shliq |
| `docker` (butun blok) | ✅ `do'ker` | matn boshi/oxiri ham chegara |
| `docker.` | ❌ tegilmaydi | o'ngida nuqta |
| `docker'ni` | ❌ tegilmaydi | o'ngida apostrof |
| `dockerfile` | ❌ tegilmaydi | boshqa so'z ichida |

Ya'ni qo'shimchali va tinish belgili shakllarni alohida kalit qilib qo'shish kerak
(`"docker'ni": "do'kerni"`). Ularni qo'lda terib chiqmaslik uchun:

```bash
.venv/bin/python utils/collect_terms.py
```

**2) Sonlar, sanalar va vaqt so'zga aylantiriladi** (`uztts.normalize`):

```
Bugun 16.07.2026, soat 14:30 da uchrashamiz.
→ Bugun o'n olti iyul ikki ming yigirma olti, soat o'n to'rt o'ttiz da uchrashamiz.
```

Namuna sifatida `terms.example.json` bor:

```bash
cp terms.example.json /path/to/docker/normalize.json
```

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

Fayl nomi — subtitrning **boshlanish vaqti**. 7-bosqich audioni videoga aynan shu nom bo'yicha joylashtiradi,
shuning uchun fayllarni qayta nomlamang.

- Model **bir marta** yuklanadi, barcha segmentlar shu jarayonda generatsiya qilinadi
- Papkada tayyor fayl bo'lsa, qayta generatsiya qilinmaydi (uzilgan jarayonni davom ettirish mumkin).
  Butunlay yangilash uchun: `rm -rf /path/to/docker/audios`
- Audio o'z oralig'iga sig'masa, avtomatik tezlashtiriladi (maksimum 1.5x)

Kursda o'qituvchi ohangi mos keladi — default `calm` hissiyoti va `xurmo.wav` ovozi shunga yaqin. Boshqasini
sinab ko'rish uchun:

```bash
rm -rf /path/to/docker/audios
NAVOIY_REFERENCE=navoiy-tts/demo/warm_agent.wav .venv/bin/python steps/generate_audios.py
```

---

### 7-bosqich — o'zbekcha audiolarni biriktirish

```bash
.venv/bin/python steps/merge_audios.py
```

```
Ovozsiz video fayl manzilini kiriting (/path/to/docker/docker-no-audio.mp4): /path/to/docker/docker-no-audio.mp4
Audiolar joylashgan papka manzilini kiriting [/path/to/docker/audios]: ⏎
```

> **Diqqat:** bu yerda asl `docker.mp4` emas, 1-bosqichdan chiqqan `docker-no-audio.mp4` berilishi kerak.
> Aks holda inglizcha nutq qaytib qo'shiladi.

Video ovozsiz bo'lgani uchun ekranda shunday chiqadi:

```
  Video ovozsiz — faqat o'zbekcha audiolar qo'shiladi.
```

**Natija:** `/path/to/docker/docker-result.mp4` — tayyor dublyaj qilingan video

---

## Fayllar xaritasi

`/path/to/docker/docker.mp4` uchun quvur oxirida:

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

---

## Kursga oid maslahatlar

**Jarayon uzilib qoldi.** Qaytadan ishga tushiring — har bir bosqich tayyor natijani qayta hisoblamaydi.

**Bir kursning barcha videolari bir xil atamalarni ishlatadi.** Shuning uchun `normalize.json` ni kurs papkasi
ildizida (`assets/docker/normalize.json`) bitta qilib saqlang — `batches/normalize_srt_batch.py` uni hamma
papkaga qo'llaydi. Bitta videoga xos atamalar bo'lsa, o'sha papkada `docker14-normalize.json` yarating.

**O'zbekcha nutq keyingi jumla ustiga chiqib ketyapti.** O'zbekcha matn inglizchadan uzunroq bo'ladi.
`steps/generate_audios.py` da `MAX_TEMPO` ni `1.8` ga ko'taring yoki `NAVOIY_SPEED=1.15` bilan generatsiya
qiling.

**Fon musiqasi kerak bo'lib qoldi.** Kurs emas, kino rejimidan foydalaning: [MOVIE.md](MOVIE.md).
