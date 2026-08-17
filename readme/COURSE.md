# Kursni o'zbek tiliga dublyaj qilish

Boshidan oxirigacha: kursni yuklab olishdan tortib, har bir darsning o'zbekcha videosini olgunga qadar.

Kurs videolarida orqa fondagi musiqa va effektlar kerak emas, shuning uchun bu yo'lda video ovozi butunlay
tashlab yuboriladi va yakuniy videoda faqat o'zbekcha nutq eshitiladi.

> Kino, film uchun [MOVIE.md](MOVIE.md) ga qarang. O'rnatish va fayllar ma'lumotnomasi —
> [README.md](../README.md) da.

**Umumiy yo'l xaritasi:**

```
1. Kursni yuklab olish            →  assets/docker/docker1, docker2, ...
2. Tayyorgarlik (1-3 bosqichlar)  →  -no-audio.mp4, .wav, .srt
3. Tarjima (4-bosqich)            →  -uz.srt
4. Atamalar lug'ati               →  terms.json → full_terms.json
   4a. avtomatik to'ldirish (fill_terms.py)      →  terms.json + not_ready_terms.json
   4b. qolganini qo'lda yozish (not_ready_terms.json)
   4c. tayyorlarini QO'LDA terms.json ga ko'chirish
   4d. shakllarni yig'ish (collect_terms.py)     →  terms/*.json, qo'lda to'g'rilanadi
   4e. birlashtirish (merge_terms.py)            →  full_terms.json
5. Normalize (5-bosqich)          →  -uz-normalized.srt   (full_terms.json ko'rsatiladi)
6. Audiolar (6-bosqich)           →  audios/*.wav
7. Yig'ish (7-bosqich)            →  -result.mp4
```

---

## 1. Kurs materiallarini olish

### Udemy

1. Microsoft Edge uchun
   [Udemy Downloader](https://microsoftedge.microsoft.com/addons/detail/udemy-downloader/nalkmdneafbahjimajlhkjnlkdgemnpl)
   kengaytmasini o'rnating.
2. Udemy profilingizga kiring, kursni oching va kengaytma orqali **butun kursni** yuklab oling.

Yuklab olingan videolar odatda `7 mening videom.mp4` ko'rinishida — nomining boshida dars raqami turadi.

### Videolarni `assets/` ga joylashtirish

```bash
.venv/bin/python utils/locate_videos.py
```

```
Videolar joylashgan absolute path: /Users/asliddin/Downloads/docker-kursi
Destination path: /Users/asliddin/Documents/projects/translate-video/assets/docker
Name: docker
```

Skript har bir video uchun alohida papka yasaydi va nomlarni tartibga soladi:

```
assets/docker/
├── docker1/
│   ├── docker1.mp4     ← video (nusxa)
│   └── README.md       ← dars nomi
├── docker2/
│   ├── docker2.mp4
│   └── README.md
└── ...
```

Bundan keyingi hamma skript aynan shu tuzilishga tayanadi: **ota papka nomi** (`docker`) ichki papkalar nomini
(`docker1`, `docker2`, …) belgilaydi, papka nomi esa ichidagi fayllar nomini belgilaydi.

> Mavjud video va `README.md` qayta yozilmaydi — skriptni bemalol qayta ishga tushirsa bo'ladi.

---

## 2. Tayyorgarlik: ovozsiz video, audio va transkripsiya

1-3 bosqichlar: video ovozidan tozalanadi, transkripsiya uchun audio ajratiladi va whisper inglizcha `.srt`
yasaydi.

**Bitta dars uchun:**

```bash
.venv/bin/python pipelines/prepare.py
```

```
Video fayl manzilini kiriting (/path/to/docker/docker.mp4): assets/docker/docker1/docker1.mp4
1) Ovozsiz video qayerga saqlansin [.../docker1-no-audio.mp4]: ⏎
2) Transkripsiya uchun audio qayerga saqlansin [.../docker1.wav]: ⏎
3) Transkripsiya .srt fayli qayerga saqlansin [.../docker1.srt]: ⏎
4) Audiodagi nutq tili (auto — o'zi aniqlaydi) [en]: ⏎
```

Barcha savollar **boshida** so'raladi — keyin dastur to'xtamasdan ishlaydi.

**Butun kurs uchun:**

```bash
.venv/bin/python batches/prepare_batch.py
```

```
Path (video papkalari joylashgan ota papka): assets/docker
Start (masalan 18 -> docker18 dan boshlanadi) [1]: 1
End (masalan 20 -> docker20 gacha, docker20 ham kiradi) [oxirigacha]: ⏎
```

Har bir papkada uch fayl paydo bo'ladi:

```
docker1/docker1-no-audio.mp4   ← ovozsiz video (7-bosqichda ishlatiladi)
docker1/docker1.wav            ← 16 kHz mono audio
docker1/docker1.srt            ← inglizcha transkripsiya
```

- Uch natijasi ham tayyor papka o'tkazib yuboriladi — uzilgan jarayonni bemalol davom ettirasiz.
- Bitta video xato bersa quvur to'xtamaydi; oxirida hisobot va umumiy vaqt chiqadi.
- Eng sekin qismi — whisper. Bir soatlik kurs uchun bir necha soat ketishi mumkin.

---

## 3. Tarjima

### 3.1. Claude Code'ni tayyorlash

Tarjima Claude Code'ning **headless** rejimi orqali bajariladi, ya'ni `claude -p` ga `.srt` matni beriladi va
u tayyor `.srt` qaytaradi.

```bash
npm install -g @anthropic-ai/claude-code
```

So'ng bir marta terminalda ishga tushirib, tizimga kiring:

```bash
claude
```

Brauzer ochiladi va hisobingizni tasdiqlaysiz. Buning uchun **Claude obunasi bo'lishi kerak** — tarjima o'sha
obuna hisobidan foydalanadi. Kirgandan keyin `claude` ni yopsangiz ham bo'ladi; keyingi chaqiruvlar shu
sessiyani ishlatadi.

### 3.2. Tarjimani ishga tushirish

**Bitta dars uchun:**

```bash
.venv/bin/python steps/translate_srt.py
```

```
Tarjima qilinadigan .srt fayl manzilini kiriting: assets/docker/docker1/docker1.srt
Tarjima qilingan .srt fayl qayerga saqlansin [.../docker1-uz.srt]: ⏎
  Yo'nalish: en -> uz | 59 ta subtitr
  Model: claude-opus-5 (effort=high) — bu biroz vaqt oladi...
  29 ta subtitr yozildi (1 daqiqa 12 soniya, $0.4137).
```

**Butun kurs uchun:**

```bash
.venv/bin/python batches/translate_batch.py
```

```
Path (video papkalari joylashgan ota papka): assets/docker
Start (masalan 14 -> docker14 dan boshlanadi) [1]: 1
End (masalan 20 -> docker20 gacha, docker20 ham kiradi) [oxirigacha]: ⏎
Qaysi tildan (til kodi) [en]: ⏎
Qaysi tilga (til kodi) [uz]: ⏎
```

```
docker1/docker1.srt  ->  docker1/docker1-uz.srt
docker2/docker2.srt  ->  docker2/docker2-uz.srt
```

Tarjima allaqachon mavjud papka o'tkazib yuboriladi. Oxirida **jami narx** ko'rsatiladi.

### 3.3. Tarjima nima qiladi

- Timestamp'lar o'zgarmaydi; gap ikki blokka bo'linib qolgan joyda bloklar birlashtiriladi va qayta
  raqamlanadi (shuning uchun bloklar soni kamayishi normal).
- **Texnik atamalar va ismlar tarjima qilinmaydi** — `container`, `Docker Compose`, `Node.js` asl yozuvida
  qoladi. Ularning o'qilishi keyingi bosqichda hal qilinadi.
- Uslub — jonli, o'qituvchi so'zlayotgandek. Transkripsiya xatolari tuzatiladi.

---

## 4. Atamalar lug'ati: `terms.json`

TTS inglizcha so'zlarni o'zbekcha o'qish qoidalari bilan talaffuz qiladi, natijada `container` ni "sontayner"
kabi noto'g'ri o'qishi mumkin. Shuning uchun har bir atamaning **o'qilishi** oldindan yozib qo'yiladi.

### 4.1. Kurs papkasi uchun `terms.json` yaratish

Tarjima tugagach, `-uz.srt` fayllarida inglizcha holida qolgan so'zlarni yig'ib olish kerak. Buni Claude Code
bilan qilish qulay — kurs papkasida `claude` ni oching:

```bash
cd assets/docker
claude
```

va shunday so'rang:

```
Shu papkadagi barcha */*-uz.srt fayllarni o'qi. Ularda inglizcha holida qolgan barcha so'zlarni
(texnik atamalar, ismlar, komandalar) yig'ib, shu papkada terms.json fayli yarat.

Talablar:
  * Kalit — .srt faylda uchragan aynan o'sha yozuv (qo'shimchasi va tinish belgisi bilan birga,
    masalan "container'lar", "container.").
  * Qiymat — bo'sh string "".
  * Takrorlanmasin, alifbo tartibida bo'lsin.
  * Faqat toza JSON — izohsiz, tekis (nested emas) tuzilishda.
```

Natija shunday bo'ladi:

```json
{
  "container": "",
  "container'lar": "",
  "container.": "",
  "Docker": "",
  "Docker'ni": "",
  "Kubernetes": ""
}
```

> **Nega qo'shimchasi bilan?** 5-bosqichdagi almashtirish so'zni faqat **ikki tomonida ham bo'shliq** bo'lganda
> almashtiradi. Ya'ni `container` kaliti `container'lar` ga ta'sir qilmaydi — har bir shakl alohida kalit
> bo'lishi kerak.

### 4.2. O'qilishlarni loyihadagi umumiy lug'atdan to'ldirish

Loyiha ildizida umumiy `terms.json` yuritiladi — unda ilgari aniqlangan o'qilishlar to'planadi
(`"docker": "do'ker"`, `"container": "konteyner"`, …). Kurs papkasidagi bo'sh qiymatlarni o'shandan
to'ldirish kerak.

```bash
.venv/bin/python utils/fill_terms.py
```

```
Kurs papkasidagi terms.json manzili: assets/docker/terms.json
Asosiy terms.json manzili [/Users/.../translate-video/terms.json]: ⏎
Allaqachon to'ldirilgan qiymatlar ham yangilansinmi? [ha/Yo'q]: ⏎
```

Ish yakunida kurs papkasida **ikkita** fayl qoladi:

```
assets/docker/
├── terms.json              ← faqat o'qilishi MA'LUM so'zlar
└── not_ready_terms.json    ← o'qilishi hali noma'lum so'zlar (qiymati bo'sh)
```

```
  To'ldirildi          : 54
  Tegilmadi (tayyor)   : 3
  O'qilishi ma'lum     : 57  -> terms.json
  O'qilishi noma'lum   : 2   -> not_ready_terms.json

  not_ready_terms.json ichidagilarni qo'lda to'ldirasiz:
    Connect
    Terraform

  To'ldirgach shu skriptni qayta ishga tushiring — ular terms.json ga o'tadi.
```

**Qoida: faqat birga-bir to'g'ri kelgan so'zlar to'ldiriladi.** So'z asosiy lug'atda aynan o'zi bo'lishi kerak
(katta-kichik harfga qaralmaydi, natijada bosh harf saqlanadi):

| Kurs lug'atidagi so'z | Asosiy lug'atda | Natija |
|---|---|---|
| `container` | `container` bor | ✅ `konteyner` |
| `Container` | `container` bor | ✅ `Konteyner` (bosh harf saqlanadi) |
| `container.` | `container.` yo'q | ❌ `not_ready_terms.json` ga |
| `container'lar` | `container'lar` yo'q | ❌ `not_ready_terms.json` ga |
| `Terraform` | yo'q | ❌ `not_ready_terms.json` ga |

Qo'shimchali va tinish belgili shakllar **taxmin qilinmaydi** — ularning har biri asosiy lug'atda alohida kalit
bo'lishi kerak. Bu ataylab shunday: taxmin qilinganda `log` atamasi tufayli `login` → `log`+`in` = `login`
kabi noto'g'ri qiymatlar sezdirmasdan yozilib ketardi.

Allaqachon to'ldirilgan qiymatlar tegilmaydi (oxirgi savolga `ha` desangiz — ular ham qayta hisoblanadi).

Yana bir yordamchi — `utils/collect_terms.py`. U allaqachon o'qilishi ma'lum atamalarning matndagi barcha
shakllarini topib, tayyor qiymat bilan chiqarib beradi:

```bash
.venv/bin/python utils/collect_terms.py
```

```
Path (video papkalari joylashgan ota papka): assets/docker
terms.json manzili [assets/docker/terms.json]: ⏎
Natija JSON fayllari qaysi papkaga saqlansin [assets/docker/terms]: ⏎
```

Kurs papkasida `terms/` papkasi paydo bo'ladi va har bir atama uchun alohida fayl yaratiladi —
`terms/container.json`:

```json
{
  "container'lar": "konteyner'lar",
  "container.": "konteyner.",
  "containerda": "konteynerda"
}
```

Bu fayllardagi qiymatlar **avtomatik chiqarilgan** — ularni ko'zdan kechirib, noto'g'rilarini to'g'rilaysiz.
So'ng hammasini bitta faylga birlashtirasiz (4.5-bo'lim).

### 4.3. Qolganini qo'lda to'ldirish

`not_ready_terms.json` ni ochib, har bir so'zning o'qilishini o'zingiz yozasiz — o'zbek lotin harflarida,
inglizcha talaffuzga asoslanib:

```json
{
  "Kubernetes": "kubernetis",
  "Kubernetes'ga": "kubernetisga",
  "deploy": "deplo'y",
  "Maximilian": "Maksimillian"
}
```

Ishonchingiz komil bo'lmasa, o'qilishni **quloq bilan tekshiring**:

```bash
.venv/bin/python utils/preview_terms.py
```

```
terms.json manzili: assets/docker/terms.json
Audiolar qaysi papkaga saqlansin [assets/docker/terms_audios]: ⏎
Qaysi so'z (hammasi uchun Enter) []: container
  1 ta atama | 0 tasi allaqachon tayyor -> assets/docker/terms_audios
  [1/1] container.wav : Endi konteyner sahifasiga kiring
```

Har bir atama `"Endi {o'qilishi} sahifasiga kiring"` gapi ichida o'qitiladi va **kalit so'z nomi** bilan
saqlanadi (`container.wav`). Tinglab, noto'g'ri o'qilayotganini topasiz.

- Oxirgi savolda **Enter** bossangiz, `terms.json` dagi **hamma** atama uchun audio yasaladi (20 tadan ko'p
  bo'lsa tasdiq so'raydi — TTS sekin).
- O'qilish har doim `terms.json` dan olinadi. So'z faylda bo'lmasa, skript to'xtaydi — avval uni faylga
  qo'shing.
- **Mavjud audio qayta yozilmaydi** — o'tkazib yuboriladi. Qaytadan tinglash uchun eski `.wav` ni o'chiring.
  Hammasi tayyor bo'lsa, TTS modeli umuman yuklanmaydi.

### 4.4. To'ldirilganlarni `terms.json` ga ko'chirish (qo'lda)

O'qilishi yozib bo'lingan yozuvlarni **qo'lda** `terms.json` ga ko'chirasiz va `not_ready_terms.json` dan
o'chirasiz:

```json
// not_ready_terms.json — faqat hali yozilmaganlari qoladi
{
  "Helm": ""
}
```

```json
// terms.json — ko'chirilganlar shu yerga qo'shiladi
{
  "container": "konteyner",
  "Kubernetes": "kubernetis",
  "Kubernetes'ga": "kubernetisga",
  "deploy": "deplo'y",
  "Maximilian": "Maksimillian"
}
```

Shu ko'chirish tugagach, kurs papkasidagi `terms.json` tayyor bo'ladi.

> Yangi aniqlangan o'qilishlarni loyiha ildizidagi umumiy `terms.json` ga ham qo'shib boring — keyingi
> kurslarda `fill_terms.py` ularni avtomatik topadi.

> Agar ko'chirishni unutib, `fill_terms.py` ni qayta ishga tushirsangiz, u `not_ready_terms.json` dagi
> to'ldirilgan yozuvlarni o'zi ham `terms.json` ga o'tkazadi — ya'ni ish yo'qolmaydi.

### 4.5. Hammasini birlashtirish: `full_terms.json`

`terms.json` da atamalarning **asosiy shakli** turadi (`container`), `terms/` papkasida esa ularning matndagi
**barcha shakllari** (`container'lar`, `container.`, `containerda`). 5-bosqich ikkalasini ham biladigan bitta
fayl kutadi — shuni yasaymiz:

```bash
.venv/bin/python utils/merge_terms.py
```

```
Path (kurs papkasi): assets/docker
Shakllar papkasi (collect_terms.py natijasi) [assets/docker/terms]: ⏎
Kurs terms.json manzili [assets/docker/terms.json]: ⏎
```

```
  terms.json: 572 ta yozuv
  terms/: 493 ta fayl, 7663 ta yozuv

  Jami yozuv         : 5770
  Bo'sh (tashlandi)  : 0
  Ziddiyat           : 0
  Natija             : assets/docker/full_terms.json
```

- Natija **alifbo tartibida** `assets/docker/full_terms.json` ga yoziladi.
- Tartib: avval `terms.json`, ustiga `terms/` papkasidagi fayllar — ya'ni **qo'lda to'g'rilagan shakllar
  ustun** turadi.
- Bir xil so'zga turlicha o'qilish uchrasa, oxirgisi olinadi va ekranda ro'yxat qilib ko'rsatiladi — ko'zdan
  kechirib chiqing.
- Qiymati bo'sh yozuvlar natijaga **qo'shilmaydi**: 5-bosqichda ular so'zni matndan o'chirib yuborardi.

`full_terms.json` — `terms.json` ning to'liq varianti (uning hamma yozuvi + shakllar). **5-bosqichda aynan shu
fayl ko'rsatiladi.**

---

## 5. Normalize: TTS uchun matn tayyorlash

Bu bosqichda 4-bo'limda tayyorlangan **kurs papkasidagi `full_terms.json`** ko'rsatiladi — atamalar aynan shu
fayldan olinadi. (`terms/` papkasini yig'magan bo'lsangiz, `terms.json` ni ko'rsatasiz — u holda faqat asosiy
shakllar almashadi.)

**Bitta dars uchun:**

```bash
.venv/bin/python steps/normalize_srt.py
```

```
Tarjima qilingan .srt fayl manzilini kiriting (...): assets/docker/docker1/docker1-uz.srt
Normalize qilingan .srt qayerga saqlansin [.../docker1-uz-normalized.srt]: ⏎
Atamalar JSON fayli manzilini kiriting (/path/to/docker/full_terms.json) (o'tkazib yuborish uchun Enter): assets/docker/full_terms.json
```

**Butun kurs uchun:**

```bash
.venv/bin/python batches/normalize_srt_batch.py
```

```
Path (video papkalari joylashgan ota papka): assets/docker
Start (masalan 14 -> docker14 dan boshlanadi) [1]: 1
End (masalan 20 -> docker20 gacha, docker20 ham kiradi) [oxirigacha]: ⏎
Tarjima tili (til kodi) [uz]: ⏎
Umumiy atamalar JSON fayli (assets/docker/full_terms.json) (o'tkazib yuborish uchun Enter): assets/docker/full_terms.json
Tayyor natijalar qayta hisoblansinmi? [ha/Yo'q]: ⏎
```

> ⚠️ Atamalar savolida qavs ichidagi manzil **default emas** — u shunchaki namuna. Enter bossangiz, atamalar
> almashtirilmaydi va faqat sonlar/sanalar so'zga aylanadi. Lug'at kerak bo'lsa, manzilni to'liq yozing.

```
docker1/docker1-uz.srt  ->  docker1/docker1-uz-normalized.srt
```

Ikki amal shu tartibda bajariladi:

**1) Atamalar almashtiriladi** (`terms.json` bo'yicha) — so'z faqat ikki tomonida bo'shliq bo'lganda:

| Matn | Natija |
|---|---|
| `docker run` | ✅ `do'ker run` |
| `docker.` | ❌ tegilmaydi (kalit sifatida `"docker."` bo'lsa — almashadi) |
| `dockerfile` | ❌ tegilmaydi |

**2) Sonlar, sanalar va vaqt so'zga aylantiriladi:**

```
Bugun 16.07.2026, soat 14:30 da uchrashamiz.
→ Bugun o'n olti iyul ikki ming yigirma olti, soat o'n to'rt o'ttiz da uchrashamiz.
```

Atamalar fayli bir marta ko'rsatiladi va butun kursga — hamma darsga — bir xil qo'llanadi.

Bosqich bepul va tez (hammasi lokal). `terms.json` ni to'ldirgach, oxirgi savolga `ha` deb javob berib
hammasini qayta hisoblang.

**Natijani tekshiring** — bir-ikki faylni ochib, atamalar to'g'ri almashganiga ishonch hosil qiling:

```bash
head -20 assets/docker/docker1/docker1-uz-normalized.srt
```

---

## 6. Audiolarni generatsiya qilish

```bash
.venv/bin/python steps/generate_audios.py
```

```
Normalize qilingan .srt fayl manzilini kiriting (...): assets/docker/docker1/docker1-uz-normalized.srt
Audiolar qaysi papkaga saqlansin [assets/docker/docker1/audios]: ⏎
```

**Natija:** `assets/docker/docker1/audios/00-00-01-500.wav`, `00-00-04-200.wav`, …

Fayl nomi — subtitrning boshlanish vaqti. 7-bosqich audioni videoga aynan shu nom bo'yicha joylashtiradi,
shuning uchun fayllarni qayta nomlamang.

- Model **bir marta** yuklanadi, barcha segmentlar shu jarayonda generatsiya qilinadi
- Papkada tayyor fayl bo'lsa, qayta generatsiya qilinmaydi (uzilgan jarayonni davom ettirish mumkin)
- Audio o'z oralig'iga sig'masa, avtomatik tezlashtiriladi (maksimum 1.5x)
- Ovozni butunlay yangilash uchun: `rm -rf assets/docker/docker1/audios`

Kurs uchun default `calm` hissiyoti va `xurmo.wav` ovozi mos keladi. Boshqa ovozni sinash:

```bash
NAVOIY_REFERENCE=navoiy-tts/demo/warm_agent.wav .venv/bin/python steps/generate_audios.py
```

> **Eslatma:** 6- va 7-bosqichlar uchun batch skript hozircha yo'q — har bir dars uchun alohida ishga
> tushirasiz. Muqobil yo'l: `modes/course.py` ni o'sha video uchun ishga tushirish — 1-5 bosqichlar tayyor
> bo'lgani uchun ular o'tkazib yuboriladi va faqat qolgan ikkitasi bajariladi.

---

## 7. Yakuniy videoni yig'ish

```bash
.venv/bin/python steps/merge_audios.py
```

```
Ovozsiz video fayl manzilini kiriting (...): assets/docker/docker1/docker1-no-audio.mp4
Audiolar joylashgan papka manzilini kiriting [assets/docker/docker1/audios]: ⏎
```

> **Diqqat:** bu yerda asl `docker1.mp4` emas, 2-bo'limda tayyorlangan `docker1-no-audio.mp4` berilishi kerak.
> Aks holda inglizcha nutq qaytib qo'shiladi.

Video ovozsiz bo'lgani uchun ekranda shunday chiqadi:

```
  Video ovozsiz — faqat o'zbekcha audiolar qo'shiladi.
```

**Natija:** `assets/docker/docker1/docker1-result.mp4` — o'zbek tilida gapiradigan tayyor dars.

---

## Yakuniy holat

Bitta dars papkasi quvur oxirida shunday ko'rinadi:

```
assets/docker/docker1/
├── README.md                   ← dars nomi
├── docker1.mp4                 ← manba (Udemy'dan)
├── docker1-no-audio.mp4        ← 1-bosqich
├── docker1.wav                 ← 2-bosqich
├── docker1.srt                 ← 3-bosqich (inglizcha)
├── docker1-uz.srt              ← 4-bosqich (o'zbekcha)
├── docker1-uz-normalized.srt   ← 5-bosqich (TTS uchun)
├── audios/                     ← 6-bosqich
│   ├── 00-00-01-500.wav
│   └── 00-00-04-200.wav
└── docker1-result.mp4          ← 7-bosqich (NATIJA)
```

Kurs papkasining ildizida esa umumiy `terms.json` turadi:

```
assets/docker/
├── terms.json              ← o'qilishi ma'lum atamalar (5-bosqich shuni ishlatadi)
├── not_ready_terms.json    ← o'qilishi hali yozilmagan so'zlar (hammasi to'lgach o'chadi)
├── docker1/
├── docker2/
└── ...
```

---

## Maslahatlar

**Jarayon uzilib qoldi.** Qaytadan ishga tushiring — har bir bosqich tayyor natijani qayta hisoblamaydi.

**Bir kursning hamma darsi bir xil atamalarni ishlatadi.** Shuning uchun `terms.json` ni kurs papkasi
ildizida bitta qilib saqlang — `normalize_srt_batch.py` uni hamma papkaga qo'llaydi.

**Atama noto'g'ri o'qilyapti.** `terms.json` dagi o'qilishini o'zgartiring va faqat 5-6 bosqichlarni qayta
bajaring (`rm -rf <papka>/audios` ni unutmang).

**O'zbekcha nutq keyingi jumla ustiga chiqib ketyapti.** `steps/generate_audios.py` da `MAX_TEMPO` ni `1.8`
ga ko'taring yoki `NAVOIY_SPEED=1.15` bilan generatsiya qiling.

**Fon musiqasi kerak bo'lib qoldi.** Kurs emas, kino yo'lidan boring: [MOVIE.md](MOVIE.md).
