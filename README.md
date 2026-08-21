# 🎬 Kino Bot (aiogram 3, Python)

Telegram uchun kino/serial bot: nom yoki kod bo'yicha qidiruv + admin panel (qo'shish/o'chirish).

## Imkoniyatlar
- Foydalanuvchi kino **nomini** yozsa — mos natijalar chiqadi (bir nechta bo'lsa, tugmalar bilan).
- Foydalanuvchi **kod** (raqam) yuborsa — to'g'ridan-to'g'ri o'sha kino/serial yuboriladi.
- **Admin panel** (`/admin`):
  - ➕ Kino qo'shish — kod, nom, tavsif so'raladi, so'ng video/faylni yuborasiz.
  - 🗑 Kino o'chirish — kod orqali.
  - 📊 Statistika — bazadagi umumiy son.
- Ixtiyoriy: majburiy kanalga obuna tekshiruvi (`config.py` da `REQUIRED_CHANNEL`).

## O'rnatish

1. Python 3.10+ o'rnatilgan bo'lishi kerak.
2. Kutubxonalarni o'rnating:
   ```bash
   pip install -r requirements.txt
   ```
3. `config.py` faylini oching va:
   - `BOT_TOKEN` — @BotFather dan olingan tokenni qo'ying.
   - `ADMIN_IDS` — o'zingizning Telegram ID raqamingizni qo'ying (bir nechta admin bo'lsa, vergul bilan ro'yxatga qo'shing). ID ni bilish uchun @userinfobot ga yozing.
   - `REQUIRED_CHANNEL` — agar majburiy obuna kerak bo'lmasa, `None` qoldiring.
4. Botni ishga tushiring:
   ```bash
   python main.py
   ```

## Fayllar tuzilishi
```
kino_bot/
├── main.py         # bot logikasi (handlerlar)
├── database.py      # SQLite bilan ishlash
├── config.py         # token, adminlar, sozlamalar
├── requirements.txt
└── README.md
```

## Kino qo'shish jarayoni (admin uchun)
1. `/admin` yoki `/add` yuboring.
2. Kod kiriting (masalan `101`).
3. Nom kiriting (masalan `Yulduzlar jangi`).
4. Tavsif kiriting yoki `/skip` bilan o'tkazib yuboring.
5. Video yoki faylni botga yuboring — saqlanadi va tayyor.

## Render.com'ga joylash (deploy)

Bu loyiha Render uchun tayyorlangan (`render.yaml`, keep-alive server allaqachon `main.py` ichida bor).

1. Loyihani GitHub'ga yuklang (repo **public bo'lsa ham xavfsiz** — token endi kodda emas, `os.environ` orqali olinadi).
2. [render.com](https://render.com) da ro'yxatdan o'ting → **New** → **Web Service** → GitHub repongizni tanlang.
3. Sozlamalar avtomatik `render.yaml` dan olinadi. Agar qo'lda kiritsangiz:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
4. **Environment** bo'limida quyidagi o'zgaruvchilarni qo'shing:
   - `BOT_TOKEN` — @BotFather dan olingan token
   - `ADMIN_IDS` — masalan `6515888800` (bir nechta bo'lsa: `6515888800,111111111`)
   - `REQUIRED_CHANNEL` — ixtiyoriy, kerak bo'lmasa bo'sh qoldiring
5. **Deploy** tugmasini bosing.

### Muhim eslatmalar (bepul tarif uchun)
- **Uxlab qolish muammosi:** Render bepul Web Service'ga 15 daqiqa HTTP so'rov kelmasa, uni to'xtatadi — bot ham to'xtaydi. Yechim: [UptimeRobot](https://uptimerobot.com) (bepul) da botning Render URL'iga (masalan `https://kino-bot.onrender.com`) har 5-10 daqiqada ping yuboradigan monitor sozlang.
- **Baza (SQLite) yo'qolishi:** Bepul tarifda disk vaqtinchalik — har deploy/restart'da `kino_bot.db` va undagi barcha kinolar o'chib ketadi. Uzoq muddat ishlatmoqchi bo'lsangiz, Render'ning bepul PostgreSQL bazasiga o'tish tavsiya etiladi (kerak bo'lsa yordam beraman).
- Token va admin ID endi `config.py` da emas, Render Environment Variables'da saqlanadi — shuning uchun kodni GitHub'ga xavfsiz yuklashingiz mumkin.

