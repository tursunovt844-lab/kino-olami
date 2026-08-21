# config.py
# Bot sozlamalari
#
# MUHIM: Token va admin ID endi bu faylda YOZILMAYDI (xavfsizlik uchun).
# Ular faqat Environment Variables (muhit o'zgaruvchilari) orqali beriladi:
#   - Lokal kompyuterda ishga tushirsangiz: ".env" fayl yarating (pastga qarang)
#   - Render.com'da: Dashboard -> Environment bo'limiga qo'shing
# Shu tufayli bu loyihani GitHub'ga (hatto public repo qilib) xavfsiz yuklash mumkin.

import os

# Lokalda ishlatish uchun: agar ".env" fayli mavjud bo'lsa, undan o'qiydi.
# (python-dotenv o'rnatilmagan bo'lsa ham xato bermaydi - shunchaki e'tiborsiz qoldiradi)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

_admin_ids_env = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_env.split(",") if x.strip()]

# Kanal majburiy obuna qilmoqchi bo'lsangiz (ixtiyoriy), kanal username sini yozing
# Masalan: "@mening_kinolar_kanalim"  yoki  None (talab qilinmasa)
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL") or None

DB_NAME = "kino_bot.db"

# Render kabi platformalar "Web Service" turi uchun portni beradi (PORT muhit o'zgaruvchisi)
PORT = int(os.environ.get("PORT", 8080))
