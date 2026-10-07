import asyncio
import aiohttp

from database import get_cached_example, save_example

DICTIONARY_API = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"


async def _fetch_from_api(word: str) -> str | None:
    """Ходит в dictionaryapi.dev. Бросает исключение при сетевой ошибке."""
    url = DICTIONARY_API.format(word=word)
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            if resp.status == 404:
                return None  # слова нет в словаре
            if resp.status != 200:
                raise RuntimeError(f"API returned {resp.status}")
            data = await resp.json()
            for entry in data:
                for meaning in entry.get("meanings", []):
                    for definition in meaning.get("definitions", []):
                        example = definition.get("example")
                        if example and example.strip():
                            return example.strip()
    return None


async def fetch_example_sentence(word: str) -> str | None:
    """
    Возвращает пример с использованием кэша.
    При сетевой ошибке возвращает None и НЕ кэширует результат.
    """
    cached = await get_cached_example(word)
    if cached is not None:
        return cached if cached else None

    try:
        sentence = await _fetch_from_api(word)
    except Exception:
        return None  # ошибка сети — не кэшируем, попробуем позже

    await save_example(word, sentence or "")
    return sentence


async def prefetch_examples(words: list[str], concurrency: int = 3) -> None:
    """
    Фоновый прогрев кэша. Уже закэшированные слова (включая пустые результаты)
    пропускаются. Параллельных запросов — не больше `concurrency`.
    """
    sem = asyncio.Semaphore(concurrency)

    async def one(word: str) -> None:
        async with sem:
            cached = await get_cached_example(word)
            if cached is not None:
                return
            try:
                sentence = await _fetch_from_api(word)
            except Exception:
                return  # сетевая ошибка — попробуем в следующий раз
            await save_example(word, sentence or "")

    await asyncio.gather(*(one(w) for w in words), return_exceptions=True)

