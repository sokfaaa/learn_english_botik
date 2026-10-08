import asyncpg
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
    )


async def init_db():
    conn = await _connect()
    try:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS words (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                en TEXT,
                ru TEXT,
                UNIQUE(user_id, en)
            )"""
        )
        # 👇 новая таблица для кэша примеров
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS examples (
                word TEXT PRIMARY KEY,
                sentence TEXT NOT NULL
            )"""
        )
    finally:
        await conn.close()


async def count_words(user_id: int) -> int:
    conn = await _connect()
    try:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM words WHERE user_id = $1", user_id
        )
    finally:
        await conn.close()


async def get_words(user_id: int):
    """Возвращает список (en, ru)."""
    conn = await _connect()
    try:
        rows = await conn.fetch(
            "SELECT en, ru FROM words WHERE user_id = $1", user_id
        )
        return [(row["en"], row["ru"]) for row in rows]
    finally:
        await conn.close()


async def get_words_with_ids(user_id: int):
    """Возвращает список (id, en, ru), отсортированный по алфавиту."""
    conn = await _connect()
    try:
        rows = await conn.fetch(
            "SELECT id, en, ru FROM words WHERE user_id = $1 ORDER BY en",
            user_id,
        )
        return [(row["id"], row["en"], row["ru"]) for row in rows]
    finally:
        await conn.close()


async def add_word(user_id: int, en: str, ru: str) -> int:
    """Возвращает 1, если вставилось, 0 если уже было."""
    conn = await _connect()
    try:
        result = await conn.execute(
            """INSERT INTO words (user_id, en, ru)
               VALUES ($1, $2, $3)
               ON CONFLICT (user_id, en) DO NOTHING""",
            user_id, en, ru,
        )
        # result вида "INSERT 0 1" или "INSERT 0 0"
        return int(result.split()[-1])
    finally:
        await conn.close()


async def delete_word(word_id: int, user_id: int) -> None:
    conn = await _connect()
    try:
        await conn.execute(
            "DELETE FROM words WHERE id = $1 AND user_id = $2",
            word_id, user_id,
        )
    finally:
        await conn.close()


async def get_recent_words(limit: int = 50) -> list[str]:
    """
    Возвращает последние N уникальных английских слов из БД.
    Используется для prefetch при запуске бота.
    """
    conn = await _connect()
    try:
        rows = await conn.fetch(
            "SELECT en FROM words GROUP BY en ORDER BY MAX(id) DESC LIMIT $1",
            limit,
        )
        return [row["en"] for row in rows]
    finally:
        await conn.close()


# ---------- Кэш примеров предложений ----------

async def get_cached_example(word: str) -> str | None:
    """
    Возвращает:
      - None — записи нет, нужно идти в API
      - ''   — запись есть, но примера нет (не ходим в API повторно)
      - '...'— готовое предложение
    """
    conn = await _connect()
    try:
        row = await conn.fetchrow(
            "SELECT sentence FROM examples WHERE word = $1",
            word.lower(),
        )
        if row is None:
            return None
        return row["sentence"]
    finally:
        await conn.close()


async def save_example(word: str, sentence: str) -> None:
    """Кладёт предложение в кэш. sentence='' разрешён — это «нет примера»."""
    conn = await _connect()
    try:
        await conn.execute(
            """INSERT INTO examples (word, sentence)
               VALUES ($1, $2)
               ON CONFLICT (word) DO UPDATE SET sentence = EXCLUDED.sentence""",
            word.lower(), sentence,
        )
    finally:
        await conn.close()