# Kinoni o'zbek tiliga dublyaj qilish

Boshidan oxirigacha: kino faylini tayyorlashdan tortib, o'zbekcha ovozli tayyor videoni olgunga qadar.

Kinoda fon musiqasi, effektlar va tabiat tovushlari ahamiyatli, shuning uchun bu yo'lda video ovozi butunlay
tashlanmaydi — **demucs orqali undan faqat odam nutqi ajratib olinadi**, fon esa joyida qoladi va yakuniy
videoda o'zbekcha nutq ostida eshitiladi.

> Kurs, ma'ruza, skrinkast uchun [COURSE.md](COURSE.md) ga qarang. O'rnatish va fayllar ma'lumotnomasi —
> [README.md](../README.md) da.

**Umumiy yo'l xaritasi:**

```
1. Faylni joylashtirish           →  assets/movies/interstellar/interstellar.mp4
2. Nutqni ajratish (1b-bosqich)   →  -removed-vocal.mp4   (demucs, sekin)
3. Audio + transkripsiya (2-3)    →  .wav, .srt
4. Tarjima (4-bosqich)            →  -uz.srt
5. Ismlar lug'ati (terms.json)    →  ixtiyoriy
6. Normalize (5-bosqich)          →  -uz-normalized.srt
7. Audiolar (6-bosqich)           →  audios/*.wav
8. Yig'ish (7-bosqich)            →  -result.mp4
```

Yoki hammasini bitta komanda bilan — [§2](#2-eng-oson-yol-butun-quvur-bitta-komanda-bilan).

---

## 1. Tayyorgarlik

### 1.1. Qo'shimcha talab: demucs

Bu yo'l demucs'ga tayanadi (model birinchi ishlatilganda ~300 MB yuklab olinadi):

```bash
.venv/bin/pip install demucs
```

### 1.2. Faylni joylashtirish

Kino bitta fayl bo'lgani uchun kurs kabi papkalarga tartiblash shart emas. Faqat **video uchun alohida papka**
oching — quvur barcha oraliq fayllarni video yoniga yozadi:

```
assets/movies/interstellar/
└── interstellar.mp4
```

### 1.3. Claude Code'ni tayyorlash

Tarjima Claude Code'ning headless rejimi orqali bajariladi:

```bash
npm install -g @anthropic-ai/claude-code
claude
```

`claude` ni bir marta ishga tushirib, brauzer orqali tizimga kiring. Buning uchun **Claude obunasi bo'lishi
kerak** — tarjima o'sha obuna hisobidan foydalanadi.

---

## 2. Eng oson yo'l: butun quvur bitta komanda bilan

```bash
.venv/bin/python modes/movie.py
```

```
Video fayl manzilini kiriting (/path/to/movie/movie.mp4): assets/movies/interstellar/interstellar.mp4
```

Quyidagi fayllar shu tartibda ishga tushadi:

```
[1/7] steps/remove_vocals.py     interstellar.mp4                -> interstellar-removed-vocal.mp4  (demucs)
[2/7] steps/extract_audio.py     interstellar.mp4                -> interstellar.wav
[3/7] steps/generate_srt.py      interstellar.wav                -> interstellar.srt
[4/7] steps/translate_srt.py     interstellar.srt                -> interstellar-uz.srt             (claude -p)
[5/7] steps/normalize_srt.py     interstellar-uz.srt             -> interstellar-uz-normalized.srt
[6/7] steps/generate_audios.py   interstellar-uz-normalized.srt  -> audios/*.wav
[7/7] steps/merge_audios.py      interstellar-removed-vocal.mp4 + audios/  -> interstellar-result.mp4
```

> **Diqqat:** 2-bosqich transkripsiya uchun **asl** videodan audio oladi (inglizcha nutq faqat o'sha yerda),
> 7-bosqich esa 1-bosqichda tayyorlangan nutqsiz videoni ishlatadi.

Dastur faqat quyidagi joylarda to'xtaydi:

1. `-removed-vocal` video mavjud bo'lsa — qayta yasashni so'raydi (Enter = yo'q)
2. `.srt` mavjud bo'lsa — qayta generatsiya qilishni so'raydi (Enter = yo'q)
3. **4-bosqich** — tarjima mavjud bo'lsa, qayta tarjima qilishni so'raydi (Enter = yo'q)
4. **5-bosqich** — atamalar JSON faylini so'raydi (kerak bo'lmasa Enter)

Kino uzun bo'lgani uchun butun jarayon bir necha soat davom etadi. Uzilib qolsa, qaytadan ishga tushiring —
tayyor natijalar qayta hisoblanmaydi.

Quyida esa har bir bosqich alohida — natijani nazorat qilib borish yoki biror bosqichni qayta bajarish uchun.

---

## 3. 1-bosqich — nutqni fondan ajratish

```bash
.venv/bin/python steps/remove_vocals.py
```

```
Video fayl manzilini kiriting (...): assets/movies/interstellar/interstellar.mp4
Nutqsiz video qayerga saqlansin [.../interstellar-removed-vocal.mp4]: ⏎
```

Ichkarida uch amal bajariladi:

1. videodan 44.1 kHz stereo audio ajratiladi (demucs shu formatni kutadi);
2. `demucs --two-stems=vocals` nutqni fondan ajratadi;
3. nutqsiz fon audiosi videoga yagona audio oqim sifatida biriktiriladi.

**Natija:** `interstellar-removed-vocal.mp4` — tasvir o'zgarmaydi (`-c:v copy`), ovozda inglizcha nutq
qolmaydi, musiqa va effektlar esa joyida. Oraliq `.wav` fayllar avtomatik o'chiriladi.

Bu **eng sekin bosqich**: CPU da taxminan real vaqtda ishlaydi (2 soatlik kino ≈ 2 soat). Apple Silicon'da:

```bash
DEMUCS_DEVICE=mps .venv/bin/python steps/remove_vocals.py
```

| O'zgaruvchi     | Default        | Izoh                                    |
|-----------------|----------------|-----------------------------------------|
| `DEMUCS_MODEL`  | `htdemucs`     | `htdemucs_ft` — sekinroq, sifatliroq    |
| `DEMUCS_DEVICE` | `cpu` / `cuda` | Apple Silicon uchun `mps`               |

> `pipelines/prepare.py` va `batches/prepare_batch.py` bu yerda **ishlatilmaydi** — ular 1-bosqichda audioni
> butunlay tashlaydi (kurs uchun). Kinoda 2- va 3-bosqichlarni quyidagicha alohida bajarasiz.

---

## 4. 2-bosqich — transkripsiya uchun audio ajratish

```bash
.venv/bin/python steps/extract_audio.py
```

```
Video fayl manzilini kiriting (...): assets/movies/interstellar/interstellar.mp4
Audio fayl qayerga saqlansin [.../interstellar.wav]: ⏎
```

**Natija:** `interstellar.wav` (16 kHz mono — whisper uchun optimal)

Bu yerga **asl** video beriladi, nutqsiz nusxa emas — transkripsiya uchun aynan nutq kerak.

---

## 5. 3-bosqich — inglizcha transkripsiya

```bash
.venv/bin/python steps/generate_srt.py
```

```
Audio fayl manzilini kiriting (...): assets/movies/interstellar/interstellar.wav
Transkripsiya .srt fayli qayerga saqlansin [.../interstellar.srt]: ⏎
Audiodagi nutq tili (auto — o'zi aniqlaydi) [en]: ⏎
```

**Natija:** `interstellar.srt`

Kinoda fon musiqasi baland bo'lsa yoki bir necha odam birga gaplashsa, transkripsiya sifati pasayadi. Shunday
holatda to'liq modelni sinab ko'ring:

```bash
WHISPER_MODEL=large-v3 .venv/bin/python steps/generate_srt.py
```

**Natijani ko'zdan kechiring** — keyingi bosqichlar shu matnga tayanadi:

```bash
head -40 assets/movies/interstellar/interstellar.srt
```

---

## 6. 4-bosqich — tarjima

```bash
.venv/bin/python steps/translate_srt.py
```

```
Tarjima qilinadigan .srt fayl manzilini kiriting: assets/movies/interstellar/interstellar.srt
Tarjima qilingan .srt fayl qayerga saqlansin [.../interstellar-uz.srt]: ⏎
  Yo'nalish: en -> uz | 1240 ta subtitr
  Model: claude-opus-5 (effort=high) — bu biroz vaqt oladi...
  810 ta subtitr yozildi (7 daqiqa 41 soniya, $3.2140).
```

**Natija:** `interstellar-uz.srt`

- Timestamp'lar o'zgarmaydi; gap ikki blokka bo'linib qolgan joyda bloklar birlashtiriladi (shuning uchun
  bloklar soni kamayishi normal).
- Ismlar tarjima qilinmaydi — asl yozuvida qoladi.

Kino uzun bo'lgani uchun bitta chaqiruv uzoq davom etadi. Kerak bo'lsa vaqt chegarasini oshiring:

```bash
CLAUDE_TIMEOUT=7200 .venv/bin/python steps/translate_srt.py
```

| O'zgaruvchi      | Default         | Izoh                        |
|------------------|-----------------|-----------------------------|
| `CLAUDE_MODEL`   | `claude-opus-5` | tarjima qiladigan model     |
| `CLAUDE_EFFORT`  | `high`          | effort darajasi             |
| `CLAUDE_TIMEOUT` | `3600`          | bitta chaqiruv uchun sekund |

---

## 7. Ismlar lug'ati: `terms.json` (ixtiyoriy)

Kinoda texnik atama kam bo'ladi, lekin **ismlar va joy nomlari** noto'g'ri o'qilishi mumkin. Ularni video
papkasida `terms.json` qilib yozib qo'yasiz:

```json
{
  "Cooper": "Kuper",
  "Cooper'ga": "Kuperga",
  "Murph": "Merf",
  "New York": "Nyu York"
}
```

Qaysi so'zlar inglizcha qolganini ko'rish uchun o'sha papkada `claude` ni ochib so'rashingiz mumkin:

```
interstellar-uz.srt faylini o'qi. Inglizcha holida qolgan barcha so'zlarni (ismlar, joy nomlari, atamalar)
yig'ib, shu papkada terms.json yarat. Kalit — .srt dagi aynan o'sha yozuv (qo'shimchasi bilan),
qiymat — bo'sh string. Alifbo tartibida, faqat toza JSON.
```

So'ng har bir qiymatni o'zbek lotin harflarida, inglizcha talaffuzga asoslanib to'ldirasiz.

> **Muhim:** almashtirish so'zni faqat **ikki tomonida ham bo'shliq** bo'lganda almashtiradi. Ya'ni `Cooper`
> kaliti `Cooper'ga` yoki `Cooper.` ga ta'sir qilmaydi — har bir shakl alohida kalit bo'lishi kerak.

Atamalar kerak bo'lmasa, keyingi bosqichda savolga shunchaki Enter bosing.

---

## 8. 5-bosqich — normalize

```bash
.venv/bin/python steps/normalize_srt.py
```

```
Tarjima qilingan .srt fayl manzilini kiriting (...): assets/movies/interstellar/interstellar-uz.srt
Normalize qilingan .srt qayerga saqlansin [.../interstellar-uz-normalized.srt]: ⏎
Atamalar JSON fayli manzilini kiriting (/path/to/docker/terms.json) (o'tkazib yuborish uchun Enter): ⏎
```

> Qavs ichidagi manzil — namuna, default emas. Enter bossangiz atamalar almashtirilmaydi (kino uchun ko'pincha
> shu yetarli). `terms.json` yaratgan bo'lsangiz, uning manzilini to'liq yozing.

**Natija:** `interstellar-uz-normalized.srt`

Sonlar, sanalar va vaqt o'qiladigan so'zlarga aylantiriladi:

```
Bugun 16.07.2026, soat 14:30 da uchrashamiz.
→ Bugun o'n olti iyul ikki ming yigirma olti, soat o'n to'rt o'ttiz da uchrashamiz.
```

`terms.json` berilgan bo'lsa, undan oldin atamalar almashtiriladi.

---

## 9. 6-bosqich — o'zbekcha audiolar

```bash
.venv/bin/python steps/generate_audios.py
```

```
Normalize qilingan .srt fayl manzilini kiriting (...): .../interstellar-uz-normalized.srt
Audiolar qaysi papkaga saqlansin [.../audios]: ⏎
```

**Natija:** `assets/movies/interstellar/audios/00-00-01-500.wav`, `00-00-04-200.wav`, …

Fayl nomi — subtitrning boshlanish vaqti. 7-bosqich audioni videoga aynan shu nom bo'yicha joylashtiradi,
shuning uchun fayllarni qayta nomlamang.

- Model **bir marta** yuklanadi, barcha segmentlar shu jarayonda generatsiya qilinadi
- Papkada tayyor fayl bo'lsa, qayta generatsiya qilinmaydi (uzilgan jarayonni davom ettirish mumkin)
- Audio o'z oralig'iga sig'masa, avtomatik tezlashtiriladi (maksimum 1.5x)
- Ovozni butunlay yangilash uchun: `rm -rf assets/movies/interstellar/audios`

Kinoda ohang muhim. Mavjud hissiyotlar: `calm`, `happy`, `excited`, `sad`, `angry`, `nervous`, `scared`,
`surprised`, `whispers`, `warm`, `gentle`, `tired`, `sighs`, `sarcastic`

```bash
NAVOIY_EMOTION=warm NAVOIY_REFERENCE=navoiy-tts/demo/long_form.wav \
  .venv/bin/python steps/generate_audios.py
```

> Hissiyot butun fayl uchun bitta bo'ladi — sahna-sahna o'zgartirish hozircha qo'llab-quvvatlanmaydi.

---

## 10. 7-bosqich — yakuniy videoni yig'ish

```bash
.venv/bin/python steps/merge_audios.py
```

```
Ovozsiz video fayl manzilini kiriting (...): .../interstellar-removed-vocal.mp4
Audiolar joylashgan papka manzilini kiriting [.../audios]: ⏎
```

> **Diqqat:** bu yerda asl `interstellar.mp4` emas, 1-bosqichdan chiqqan `interstellar-removed-vocal.mp4`
> berilishi kerak. Aks holda inglizcha nutq qaytib qo'shiladi.

Videoda fon ovozi borligi uchun ekranda shunday chiqadi:

```
  Videoning o'z ovozi ham aralashmaga qo'shiladi (volume=1.0).
```

**Natija:** `interstellar-result.mp4` — fon musiqasi va o'zbekcha nutq aralashgan tayyor kino.

**Fon baland tuyulsa**, [steps/merge_audios.py](../steps/merge_audios.py) dagi `ORIGINAL_VOLUME` ni `0.3`–`0.6`
ga tushiring va faqat shu bosqichni qayta ishga tushiring — u tez ishlaydi, video qayta kodlanmaydi.

---

## Yakuniy holat

```
assets/movies/interstellar/
├── interstellar.mp4                 ← manba
├── interstellar-removed-vocal.mp4   ← 1-bosqich (nutqsiz, fon ovozi bilan)
├── interstellar.wav                 ← 2-bosqich
├── interstellar.srt                 ← 3-bosqich (inglizcha)
├── interstellar-uz.srt              ← 4-bosqich (o'zbekcha)
├── terms.json                       ← ismlar lug'ati (ixtiyoriy)
├── interstellar-uz-normalized.srt   ← 5-bosqich (TTS uchun)
├── audios/                          ← 6-bosqich
│   ├── 00-00-01-500.wav
│   └── 00-00-04-200.wav
└── interstellar-result.mp4          ← 7-bosqich (NATIJA)
```

---

## Maslahatlar

**1-bosqich juda sekin.** Demucs kinoning butun uzunligini qayta ishlaydi. `DEMUCS_DEVICE=mps` ni sinab
ko'ring; ishlamasa, tunda qoldiring — natija saqlanadi va keyingi ishga tushirishda qayta hisoblanmaydi.

**Fon ovozi nutqni bosib ketyapti.** `ORIGINAL_VOLUME` ni pasaytiring (10-bo'lim).

**Demucs fonni ham buzib qo'ydi.** Ba'zi yozuvlarda nutq va musiqa qattiq aralashgan bo'ladi. Boshqa modelni
sinab ko'ring: `DEMUCS_MODEL=htdemucs_ft` (sekinroq, sifatliroq).

**O'zbekcha nutq keyingi jumla ustiga chiqib ketyapti.** `steps/generate_audios.py` da `MAX_TEMPO` ni `1.8`
ga ko'taring yoki `NAVOIY_SPEED=1.15` bilan generatsiya qiling.

**Original ovoz umuman kerak emas.** Unda kino emas, kurs yo'li kerak: [COURSE.md](COURSE.md).

**Jarayon uzilib qoldi.** Qaytadan ishga tushiring — har bir bosqich tayyor natijani qayta hisoblamaydi.
