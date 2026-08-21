# database.py
# SQLite bilan ishlash uchun barcha funksiyalar shu yerda.
# HAR BIR funksiya xatolikni ushlab qoladi (try/except) -> baza bilan bog'liq
# hech qanday xatolik butun botni yiqitmaydi, faqat log'ga yoziladi.

import sqlite3
import logging
from contextlib import contextmanager
from config import DB_NAME

logger = logging.getLogger("database")


@contextmanager
def get_connection():
    """Bazaga ulanadi va ish tugagach albatta yopadi (xatolik bo'lsa ham)."""
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Bazani va jadvalni yaratadi (agar mavjud bo'lmasa)."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    file_id TEXT NOT NULL,
                    content_type TEXT NOT NULL,  -- 'video' yoki 'document'
                    category TEXT DEFAULT 'kino',
                    added_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_movies_code ON movies(code)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title)")
            conn.commit()
        logger.info("Baza tayyor.")
    except sqlite3.Error:
        logger.exception("Bazani yaratishda xatolik yuz berdi")
        raise  # bu yerda davom etishning ma'nosi yo'q, bot bazasiz ishlay olmaydi


def add_movie(code, title, file_id, content_type, description="", category="kino", added_by=None):
    """Yangi kino qo'shadi. Muvaffaqiyatli bo'lsa True, xato bo'lsa False qaytaradi."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO movies (code, title, description, file_id, content_type, category, added_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (code, title, description, file_id, content_type, category, added_by),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Kod band bo'lgani uchun qo'shilmadi: {code}")
        return False
    except sqlite3.Error:
        logger.exception("Kino qo'shishda xatolik")
        return False


def code_exists(code):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM movies WHERE code = ?", (code,))
            return cur.fetchone() is not None
    except sqlite3.Error:
        logger.exception("code_exists tekshirishda xatolik")
        return False


def get_movie_by_code(code):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM movies WHERE code = ?", (code,))
            return cur.fetchone()
    except sqlite3.Error:
        logger.exception("get_movie_by_code xatoligi")
        return None


def search_movies(query):
    """Nom BO'YICHA ham, kod BO'YICHA ham qidiradi (aniq va qisman mos kelishlar)."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT *,
                       CASE WHEN code = ? THEN 0 ELSE 1 END AS exact_match
                FROM movies
                WHERE code = ? OR code LIKE ? OR title LIKE ?
                ORDER BY exact_match ASC, created_at DESC
                LIMIT 20
                """,
                (query, query, f"%{query}%", f"%{query}%"),
            )
            return cur.fetchall()
    except sqlite3.Error:
        logger.exception("search_movies xatoligi")
        return []


def delete_movie(code):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM movies WHERE code = ?", (code,))
            deleted = cur.rowcount
            conn.commit()
            return deleted > 0
    except sqlite3.Error:
        logger.exception("delete_movie xatoligi")
        return False


def get_all_movies(limit=50):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM movies ORDER BY created_at DESC LIMIT ?", (limit,))
            return cur.fetchall()
    except sqlite3.Error:
        logger.exception("get_all_movies xatoligi")
        return []


def count_movies():
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as c FROM movies")
            row = cur.fetchone()
            return row["c"] if row else 0
    except sqlite3.Error:
        logger.exception("count_movies xatoligi")
        return 0
