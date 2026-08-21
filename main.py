# main.py
# Kino/serial bot - qidiruv (nom va kod bo'yicha) + admin panel (qo'shish/o'chirish)
# Ishga tushirish: python main.py
#
# BU FAYL MAXSUS "XATOLIKKA CHIDAMLI" QILIB YOZILGAN:
#  - har bir handler ichidagi kutilmagan xatolik alohida ushlanadi va logga yoziladi,
#    lekin bot ishlashda davom etadi (foydalanuvchiga tushunarli xabar chiqadi);
#  - global error-handler orqali HAR QANDAY handler ichidagi xatolik ushlanadi;
#  - noto'g'ri/eskirgan file_id, tarmoq uzilishi, Telegram API xatoliklari alohida
#    qayta ishlanadi;
#  - polling uzilib qolsa, bot avtomatik qayta urinadi (butunlay o'chib qolmaydi);
#  - startup vaqtida token/majburiy sozlamalar tekshiriladi.

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    ErrorEvent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramNetworkError
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from config import BOT_TOKEN, ADMIN_IDS, REQUIRED_CHANNEL, PORT
import database as db

# ---------------------------------------------------------------------------
# Logging: konsolga HAM, faylga HAM yoziladi -> xatolik bo'lsa keyin ko'rish oson
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("kino_bot")

# ---------------------------------------------------------------------------
# Ishga tushishdan oldingi tekshiruvlar (fail-fast: xato bo'lsa tushunarli xabar bilan to'xtaydi)
# ---------------------------------------------------------------------------

if not BOT_TOKEN or BOT_TOKEN.strip() == "" or "SIZNING" in BOT_TOKEN:
    logger.critical("BOT_TOKEN sozlanmagan! config.py yoki Environment Variables ni tekshiring.")
    sys.exit(1)

if not ADMIN_IDS:
    logger.warning("ADMIN_IDS bo'sh! Hech kim admin panelga kira olmaydi.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ---------------------------------------------------------------------------
# Yordamchi funksiyalar
# ---------------------------------------------------------------------------

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Kino qo'shish"), KeyboardButton(text="🗑 Kino o'chirish")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="❌ Admin panelni yopish")],
        ],
        resize_keyboard=True,
    )


async def check_subscription(user_id: int) -> bool:
    """Agar REQUIRED_CHANNEL sozlangan bo'lsa, foydalanuvchi obuna bo'lganini tekshiradi.
    Har qanday xatolikda (kanal topilmadi, bot admin emas va h.k.) bloklamaymiz -
    aks holda bitta noto'g'ri sozlama butun botni ishlamay qo'yadi."""
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status not in ("left", "kicked")
    except TelegramAPIError:
        logger.warning("Kanal obunasini tekshirishda Telegram xatoligi (o'tkazib yuborildi)", exc_info=True)
        return True
    except Exception:
        logger.exception("check_subscription kutilmagan xatolik (o'tkazib yuborildi)")
        return True


async def safe_answer(message: Message, text: str, **kwargs):
    """message.answer() ni xavfsiz chaqiradi - tarmoq/Telegram xatoligida bot yiqilmaydi."""
    try:
        await message.answer(text, **kwargs)
    except TelegramNetworkError:
        logger.warning("Tarmoq xatoligi tufayli xabar yuborilmadi")
    except TelegramAPIError:
        logger.exception("Telegram API xatoligi (xabar yuborilmadi)")
    except Exception:
        logger.exception("Kutilmagan xatolik (xabar yuborilmadi)")


# ---------------------------------------------------------------------------
# FSM holatlar (admin kino qo'shish jarayoni uchun)
# ---------------------------------------------------------------------------

class AddMovie(StatesGroup):
    waiting_code = State()
    waiting_title = State()
    waiting_description = State()
    waiting_file = State()


class DeleteMovie(StatesGroup):
    waiting_code = State()


MAX_CODE_LEN = 32
MAX_TITLE_LEN = 200
MAX_DESC_LEN = 1000


# ---------------------------------------------------------------------------
# Oddiy foydalanuvchi buyruqlari
# ---------------------------------------------------------------------------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        "🎬 <b>Kino botga xush kelibsiz!</b>\n\n"
        "Kino yoki serial topish uchun:\n"
        "• Nomini yozing (masalan: <i>Yulduzlar jangi</i>)\n"
        "• Yoki kodini yuboring (masalan: <code>1023</code>)\n\n"
        "Qidirishni boshlang! 🔎"
    )
    await safe_answer(message, text, parse_mode="HTML")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await safe_answer(
        message,
        "ℹ️ Kino nomini yoki kodini yozib yuboring — men sizga topib beraman.\n"
        "Masalan: <code>117</code> yoki <i>Avatar</i>",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# ADMIN: panelni ochish
# ---------------------------------------------------------------------------

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await safe_answer(message, "⛔️ Sizda admin huquqi yo'q.")
        return
    await safe_answer(message, "👑 Admin panelga xush kelibsiz!", reply_markup=admin_menu_kb())


@dp.message(F.text == "❌ Admin panelni yopish")
async def close_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await safe_answer(message, "Admin panel yopildi.", reply_markup=ReplyKeyboardRemove())


@dp.message(F.text == "📊 Statistika")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    count = db.count_movies()
    await safe_answer(message, f"📊 Bazada jami: <b>{count} ta</b> kino/serial bor.", parse_mode="HTML")


# ---------------------------------------------------------------------------
# ADMIN: Kino qo'shish (FSM orqali bosqichma-bosqich)
# ---------------------------------------------------------------------------

@dp.message(F.text == "➕ Kino qo'shish")
@dp.message(Command("add"))
async def add_movie_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await safe_answer(message, "⛔️ Sizda admin huquqi yo'q.")
        return
    await state.set_state(AddMovie.waiting_code)
    await safe_answer(
        message,
        "🔢 Yangi kino/serial uchun <b>kod</b> kiriting (masalan: 101).\n"
        "Bekor qilish uchun /cancel yozing.",
        parse_mode="HTML",
    )


@dp.message(Command("cancel"))
async def cancel_fsm(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        return
    await state.clear()
    await safe_answer(
        message,
        "❌ Amal bekor qilindi.",
        reply_markup=admin_menu_kb() if is_admin(message.from_user.id) else ReplyKeyboardRemove(),
    )


@dp.message(AddMovie.waiting_code)
async def add_movie_code(message: Message, state: FSMContext):
    if not message.text:
        await safe_answer(message, "⚠️ Iltimos matn (kod) yuboring.")
        return
    code = message.text.strip()

    if not code:
        await safe_answer(message, "⚠️ Kod bo'sh bo'lishi mumkin emas. Qaytadan kiriting:")
        return
    if len(code) > MAX_CODE_LEN:
        await safe_answer(message, f"⚠️ Kod juda uzun (maksimal {MAX_CODE_LEN} belgi). Qaytadan kiriting:")
        return
    if db.code_exists(code):
        await safe_answer(message, "⚠️ Bu kod band. Boshqa kod kiriting:")
        return

    await state.update_data(code=code)
    await state.set_state(AddMovie.waiting_title)
    await safe_answer(message, "📝 Endi kino/serial <b>nomini</b> kiriting:", parse_mode="HTML")


@dp.message(AddMovie.waiting_title)
async def add_movie_title(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await safe_answer(message, "⚠️ Iltimos nom (matn) kiriting:")
        return
    title = message.text.strip()[:MAX_TITLE_LEN]
    await state.update_data(title=title)
    await state.set_state(AddMovie.waiting_description)
    await safe_answer(message, "✏️ Qisqacha tavsif kiriting (yoki o'tkazib yuborish uchun /skip yozing):")


@dp.message(AddMovie.waiting_description, Command("skip"))
async def add_movie_desc_skip(message: Message, state: FSMContext):
    await state.update_data(description="")
    await state.set_state(AddMovie.waiting_file)
    await safe_answer(message, "🎞 Endi kino faylini (video yoki hujjat shaklida) yuboring:")


@dp.message(AddMovie.waiting_description)
async def add_movie_desc(message: Message, state: FSMContext):
    desc = (message.text or "").strip()[:MAX_DESC_LEN]
    await state.update_data(description=desc)
    await state.set_state(AddMovie.waiting_file)
    await safe_answer(message, "🎞 Endi kino faylini (video yoki hujjat shaklida) yuboring:")


async def _finalize_add_movie(message: Message, state: FSMContext, file_id: str, content_type: str):
    data = await state.get_data()
    # Ma'lumotlar FSM'da yo'qolib qolgan bo'lsa (masalan bot qayta ishga tushgan bo'lsa)
    if "code" not in data or "title" not in data:
        await state.clear()
        await safe_answer(
            message,
            "⚠️ Jarayon ma'lumotlari topilmadi (ehtimol bot qayta ishga tushgan). "
            "Iltimos /add dan qaytadan boshlang.",
        )
        return

    ok = db.add_movie(
        code=data["code"],
        title=data["title"],
        file_id=file_id,
        content_type=content_type,
        description=data.get("description", ""),
        added_by=message.from_user.id,
    )
    await state.clear()

    if ok:
        await safe_answer(
            message,
            f"✅ Saqlandi!\n🎬 <b>{data['title']}</b>\n🔢 Kod: <code>{data['code']}</code>",
            parse_mode="HTML",
            reply_markup=admin_menu_kb(),
        )
    else:
        await safe_answer(
            message,
            "❌ Saqlashda xatolik yuz berdi (kod band bo'lishi mumkin). Qaytadan /add bilan urinib ko'ring.",
            reply_markup=admin_menu_kb(),
        )


@dp.message(AddMovie.waiting_file, F.video)
async def add_movie_file_video(message: Message, state: FSMContext):
    await _finalize_add_movie(message, state, message.video.file_id, "video")


@dp.message(AddMovie.waiting_file, F.document)
async def add_movie_file_document(message: Message, state: FSMContext):
    await _finalize_add_movie(message, state, message.document.file_id, "document")


@dp.message(AddMovie.waiting_file)
async def add_movie_file_wrong(message: Message):
    await safe_answer(message, "⚠️ Iltimos video yoki fayl (hujjat) shaklida yuboring. Bekor qilish uchun /cancel.")


# ---------------------------------------------------------------------------
# ADMIN: Kino o'chirish
# ---------------------------------------------------------------------------

@dp.message(F.text == "🗑 Kino o'chirish")
@dp.message(Command("delete"))
async def delete_movie_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await safe_answer(message, "⛔️ Sizda admin huquqi yo'q.")
        return
    await state.set_state(DeleteMovie.waiting_code)
    await safe_answer(message, "🔢 O'chirmoqchi bo'lgan kino kodini kiriting:")


@dp.message(DeleteMovie.waiting_code)
async def delete_movie_code(message: Message, state: FSMContext):
    if not message.text:
        await safe_answer(message, "⚠️ Iltimos kod (matn) yuboring.")
        return
    code = message.text.strip()
    ok = db.delete_movie(code)
    await state.clear()
    if ok:
        await safe_answer(message, f"🗑 <code>{code}</code> kodli kino o'chirildi.", parse_mode="HTML", reply_markup=admin_menu_kb())
    else:
        await safe_answer(message, f"⚠️ <code>{code}</code> kodli kino topilmadi.", parse_mode="HTML", reply_markup=admin_menu_kb())


# ---------------------------------------------------------------------------
# QIDIRUV: kod yoki nom bo'yicha (oddiy matnli xabarlar shu yerga tushadi)
# ---------------------------------------------------------------------------

async def send_movie(chat_id: int, movie_row) -> bool:
    """Kino/serial faylini yuboradi. Muvaffaqiyatli bo'lsa True qaytaradi.
    Fayl ID eskirgan/noto'g'ri bo'lsa, foydalanuvchiga tushunarli xabar chiqadi
    va bot yiqilmaydi."""
    caption = f"🎬 <b>{movie_row['title']}</b>\n🔢 Kod: <code>{movie_row['code']}</code>"
    if movie_row["description"]:
        caption += f"\n\n{movie_row['description']}"

    try:
        if movie_row["content_type"] == "video":
            await bot.send_video(chat_id, movie_row["file_id"], caption=caption, parse_mode="HTML")
        else:
            await bot.send_document(chat_id, movie_row["file_id"], caption=caption, parse_mode="HTML")
        return True
    except TelegramBadRequest:
        logger.warning(f"Noto'g'ri/eskirgan file_id: kod={movie_row['code']}", exc_info=True)
        try:
            await bot.send_message(
                chat_id,
                "😔 Kechirasiz, bu fayl vaqtincha mavjud emas (o'chirilgan yoki eskirgan). "
                "Admin bilan bog'laning.",
            )
        except Exception:
            pass
        return False
    except TelegramNetworkError:
        logger.warning("Tarmoq xatoligi tufayli fayl yuborilmadi", exc_info=True)
        try:
            await bot.send_message(chat_id, "⚠️ Tarmoqda muammo, birozdan so'ng qaytadan urinib ko'ring.")
        except Exception:
            pass
        return False
    except TelegramAPIError:
        logger.exception(f"Telegram API xatoligi: kod={movie_row['code']}")
        try:
            await bot.send_message(chat_id, "⚠️ Faylni yuborishda xatolik yuz berdi. Birozdan so'ng qaytadan urinib ko'ring.")
        except Exception:
            pass
        return False
    except Exception:
        logger.exception(f"Kutilmagan xatolik: kod={movie_row['code']}")
        return False


@dp.callback_query(F.data.startswith("get_"))
async def callback_get_movie(call: CallbackQuery):
    try:
        code = call.data.split("_", 1)[1]
        movie = db.get_movie_by_code(code)
        if movie:
            await send_movie(call.message.chat.id, movie)
        else:
            await call.answer("Topilmadi", show_alert=True)
            return
        await call.answer()
    except Exception:
        logger.exception("callback_get_movie xatoligi")
        try:
            await call.answer("Xatolik yuz berdi, qaytadan urinib ko'ring.", show_alert=True)
        except Exception:
            pass


@dp.message(F.text)
async def search_handler(message: Message):
    # Admin panel tugmalari yuqorida alohida ushlanadi, shu yerga faqat qidiruv so'zlari tushadi
    text = (message.text or "").strip()
    if not text:
        return

    if REQUIRED_CHANNEL:
        subscribed = await check_subscription(message.from_user.id)
        if not subscribed:
            await safe_answer(
                message,
                f"⚠️ Botdan foydalanish uchun avval {REQUIRED_CHANNEL} kanaliga obuna bo'ling, "
                "so'ng qaytadan urinib ko'ring.",
            )
            return

    # Avval kod bo'yicha ANIQ moslikni tekshiramiz (masalan foydalanuvchi "12" yozsa)
    exact = db.get_movie_by_code(text)
    if exact:
        await send_movie(message.chat.id, exact)
        return

    # Aniq mos kelmasa — kod va nom bo'yicha umumiy (qisman) qidiruv
    results = db.search_movies(text)
    if not results:
        await safe_answer(message, "😔 Hech narsa topilmadi. Boshqa nom bilan urinib ko'ring.")
        return

    if len(results) == 1:
        await send_movie(message.chat.id, results[0])
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{row['title']} ({row['code']})", callback_data=f"get_{row['code']}")]
            for row in results
        ]
    )
    await safe_answer(message, f"🔎 {len(results)} ta natija topildi, birini tanlang:", reply_markup=kb)


# ---------------------------------------------------------------------------
# GLOBAL ERROR HANDLER
# Har qanday handler ichida kutilmagan xatolik yuz bersa, shu yerga tushadi.
# Bot HECH QACHON shu sabab bilan yiqilib qolmaydi.
# ---------------------------------------------------------------------------

@dp.errors()
async def global_error_handler(event: ErrorEvent):
    logger.exception(
        f"Ushlanmagan xatolik: update={event.update.update_id if event.update else '?'}",
        exc_info=event.exception,
    )
    try:
        chat_id = None
        if event.update.message:
            chat_id = event.update.message.chat.id
        elif event.update.callback_query and event.update.callback_query.message:
            chat_id = event.update.callback_query.message.chat.id
        if chat_id:
            await bot.send_message(chat_id, "⚠️ Kutilmagan xatolik yuz berdi. Qaytadan urinib ko'ring yoki /start bosing.")
    except Exception:
        logger.exception("global_error_handler ichida ham xatolik (e'tiborsiz qoldirildi)")
    return True  # xatolik "hal qilindi" deb belgilanadi, dispatcher davom etadi


# ---------------------------------------------------------------------------
# Render.com kabi platformalar uchun "keep-alive" mini web-server
# ---------------------------------------------------------------------------

async def health(request):
    return web.Response(text="Bot ishlayapti ✅")


async def start_web_server():
    try:
        app = web.Application()
        app.router.add_get("/", health)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"Keep-alive server {PORT}-portda ishga tushdi")
    except Exception:
        # Web-server ishga tushmasa ham, bot o'zi (polling) baribir ishlashda davom etsin
        logger.exception("Keep-alive server ishga tushmadi (bot baribir davom etadi)")


# ---------------------------------------------------------------------------
# Ishga tushirish (polling uzilib qolsa - avtomatik qayta urinadi, cheksiz to'xtamaydi)
# ---------------------------------------------------------------------------

async def main():
    db.init_db()
    await start_web_server()

    retry_delay = 5
    while True:
        try:
            logger.info("Bot polling boshlandi...")
            await dp.start_polling(bot)
        except asyncio.CancelledError:
            raise
        except TelegramNetworkError:
            logger.warning(f"Tarmoq uzildi, {retry_delay}s dan keyin qayta urinamiz...", exc_info=True)
            await asyncio.sleep(retry_delay)
        except Exception:
            logger.exception(f"Polling kutilmagan xatolik bilan to'xtadi, {retry_delay}s dan keyin qayta urinamiz...")
            await asyncio.sleep(retry_delay)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi (KeyboardInterrupt).")
