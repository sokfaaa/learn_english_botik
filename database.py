import aiosqlite
from config import DB


async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                en TEXT,
                ru TEXT,
                UNIQUE(user_id, en)
            )"""
        )
        # 👇 новая таблица для кэша примеров
        await db.execute(
            """CREATE TABLE IF NOT EXISTS examples (
                word TEXT PRIMARY KEY,
                sentence TEXT NOT NULL
            )"""
        )
        await db.commit()


async def count_words(user_id: int) -> int:
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM words WHERE user_id = ?", (user_id,)
        ) as cur:
            return (await cur.fetchone())[0]


async def get_words(user_id: int):
    """Возвращает список (en, ru)."""
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT en, ru FROM words WHERE user_id = ?", (user_id,)
        ) as cur:
            return await cur.fetchall()


async def get_words_with_ids(user_id: int):
    """Возвращает список (id, en, ru), отсортированный по алфавиту."""
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT id, en, ru FROM words WHERE user_id = ? ORDER BY en", (user_id,)
        ) as cur:
            return await cur.fetchall()


async def add_word(user_id: int, en: str, ru: str) -> int:
    """Возвращает 1, если вставилось, 0 если уже было."""
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO words (user_id, en, ru) VALUES (?, ?, ?)",
            (user_id, en, ru),
        )
        await db.commit()
        return cur.rowcount


async def delete_word(word_id: int, user_id: int) -> None:
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "DELETE FROM words WHERE id = ? AND user_id = ?", (word_id, user_id)
        )
        await db.commit()


async def get_recent_words(limit: int = 50) -> list[str]:
    """
    Возвращает последние N уникальных английских слов из БД.
    Используется для prefetch при запуске бота.
    """
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT en FROM words GROUP BY en ORDER BY MAX(id) DESC LIMIT ?",
            (limit,),
        ) as cur:
            return [row[0] for row in await cur.fetchall()]


# ---------- Кэш примеров предложений ----------

async def get_cached_example(word: str) -> str | None:
    """
    Возвращает:
      - None — записи нет, нужно идти в API
      - ''   — запись есть, но примера нет (не ходим в API повторно)
      - '...'— готовое предложение
    """
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT sentence FROM examples WHERE word = ?", (word.lower(),)
        ) as cur:
            row = await cur.fetchone()
            if row is None:
                return None
            return row[0]


async def save_example(word: str, sentence: str) -> None:
    """Кладёт предложение в кэш. sentence='' разрешён — это «нет примера»."""
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO examples (word, sentence) VALUES (?, ?)",
            (word.lower(), sentence),
        )
        await db.commit()