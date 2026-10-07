import random
import re
import aiohttp

from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from states import Exercise
from database import count_words, get_words
from handlers.examples import fetch_example_sentence
router = Router()



# ---------- Справочник типов упражнений ----------
# Ключ — код (используется в callback и в state),
# значение — текст на кнопке.
EXERCISE_TYPES = {
    "en_ru":      "🇬🇧 Перевод EN → RU",
    "fill_blank": "📝 Заполни пропуск",
}


# ---------- Утилиты для fill_blank ----------
def replace_word_with_blank(sentence: str, word: str) -> str:
    forms = [word, word + "s", word + "es", word + "ed", word + "ing", word + "d"]
    for form in sorted(set(forms), key=len, reverse=True):
        pattern = re.compile(r"\b" + re.escape(form) + r"\b", re.IGNORECASE)
        new_sentence = pattern.sub("___", sentence)
        if new_sentence != sentence:
            return new_sentence
    return sentence


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def generate_fill_blank(
    words: list[tuple[str, str]],
    excluded_words: set[str] | None = None,
):
    if len(words) < 4:
        return None

    excluded_words = excluded_words or set()

    candidates = [
        (en, ru)
        for en, ru in words
        if en not in excluded_words
    ]

    random.shuffle(candidates)

    for en_word, _ in candidates:
        example = await fetch_example_sentence(en_word)

        if not example:
            continue

        sentence_with_blank = replace_word_with_blank(example, en_word)

        if sentence_with_blank == example:
            continue

        distractors_pool = [w for w, _ in words if w != en_word]

        if len(distractors_pool) < 3:
            return None

        distractors = random.sample(distractors_pool, 3)
        options = distractors + [en_word]
        random.shuffle(options)

        return {
            "sentence": sentence_with_blank,
            "options": options,
            "correct_index": options.index(en_word),
            "correct_word": en_word,
        }

    return None

# ---------- /exercise: шаг 1 — сколько ----------

@router.message(Command("exercise"))
async def exercise_start(message: types.Message, state: FSMContext):
    count = await count_words(message.from_user.id)
    if count < 4:
        await message.answer("Нужно минимум 4 слова. Добавь через /add или /add_many")
        return

    await message.answer(
        "Сколько упражнений сделать? Отправь число (например, 10).\n"
        "Отмена — /cancel"
    )
    await state.set_state(Exercise.waiting_count)


@router.message(Exercise.waiting_count)
async def exercise_count(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Нужно число. Попробуй ещё раз или /cancel")
        return

    total = int(text)
    if total < 1 or total > 50:
        await message.answer("Число должно быть от 1 до 50.")
        return

    await state.update_data(total=total, done=0, correct=0)

    # строим клавиатуру выбора типа
    rows = [[InlineKeyboardButton(text="🎲 Рандом", callback_data="etype|random")]]
    for code, label in EXERCISE_TYPES.items():
        rows.append([InlineKeyboardButton(text=label, callback_data=f"etype|{code}")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer("Какое упражнение делаем?", reply_markup=kb)
    await state.set_state(Exercise.waiting_type)


# ---------- /exercise: шаг 2 — какое ----------

@router.callback_query(
    lambda c: c.data and c.data.startswith("etype|"), Exercise.waiting_type
)
async def exercise_type_chosen(callback: types.CallbackQuery, state: FSMContext):
    code = callback.data.split("|", 1)[1]

    if code == "random":
        chosen = "random"
        label = "🎲 Рандом"
    else:
        chosen = code
        label = EXERCISE_TYPES.get(code, code)

    await state.update_data(choice=chosen)

    await callback.message.edit_text(f"Тип: {label}\nНачинаем!")
    await state.set_state(Exercise.in_progress)

    await send_question(
        callback.bot, callback.message.chat.id, state, callback.from_user.id
    )
    await callback.answer()


# ---------- Генерация вопроса ----------

async def send_question(bot: Bot, chat_id: int, state: FSMContext, user_id: int):
    data = await state.get_data()
    done = data.get("done", 0) + 1
    total = data["total"]
    choice = data.get("choice", "random")

    words = await get_words(user_id)

    # определяем конкретный тип для этого вопроса
    if choice == "random":
        exercise_type = random.choice(list(EXERCISE_TYPES.keys()))
    else:
        exercise_type = choice

    # --- fill_blank ---
    if exercise_type == "fill_blank":
        used_fill_words = set(data.get("used_fill_words", []))
        fb = await generate_fill_blank(
        words,
        excluded_words=used_fill_words,)
        if fb:
            used_fill_words.add(fb["correct_word"])
            await state.update_data(
                type="fill_blank",
                correct_index=fb["correct_index"],
                correct_word=fb["correct_word"],
                used_fill_words=list(used_fill_words),
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=opt, callback_data=f"ans|{i}")]
                    for i, opt in enumerate(fb["options"])
                ]
            )
            await bot.send_message(
                chat_id,
                f"Вопрос {done}/{total}\n\n"
                f"Заполни пропуск:\n\n<b>{escape_html(fb['sentence'])}</b>",
                reply_markup=kb,
                parse_mode="HTML",
            )
            return
        # если не получилось — фолбэк на en_ru
        # (но если пользователь выбрал конкретно fill_blank,
        #  можно попробовать ещё раз — здесь для простоты фолбэк)

    # --- en_ru (и фолбэк) ---
    correct_en, correct_ru = random.choice(words)
    others = [ru for en, ru in words if en != correct_en]
    distractors = random.sample(others, min(3, len(others)))
    options = distractors + [correct_ru]
    random.shuffle(options)
    correct_index = options.index(correct_ru)

    await state.update_data(
        type="en_ru",
        correct_index=correct_index,
        correct_en=correct_en,
        correct_ru=correct_ru,
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=opt, callback_data=f"ans|{i}")]
            for i, opt in enumerate(options)
        ]
    )
    await bot.send_message(
        chat_id,
        f"Вопрос {done}/{total}\n\nВыбери перевод: <b>{correct_en}</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )


# ---------- Проверка ответа ----------

@router.callback_query(
    lambda c: c.data and c.data.startswith("ans|"), Exercise.in_progress
)
async def check_answer(callback: types.CallbackQuery, state: FSMContext):
    chosen = int(callback.data.split("|", 1)[1])
    data = await state.get_data()

    correct_index = data["correct_index"]
    exercise_type = data.get("type", "en_ru")
    done = data["done"] + 1
    correct = data["correct"] + (1 if chosen == correct_index else 0)
    total = data["total"]

    await callback.message.delete()

    if chosen == correct_index:
        feedback = "Верно! ✅"
    else:
        if exercise_type == "fill_blank":
            correct_answer = data.get("correct_word", "")
        else:
            correct_answer = data.get("correct_ru", "")
        feedback = f"Неверно. Правильный ответ: <b>{escape_html(correct_answer)}</b>"

    if done >= total:
        await callback.message.answer(
            f"{feedback}\n\n"
            f"🏁 Сессия завершена!\n"
            f"Правильных ответов: {correct}/{total}",
            parse_mode="HTML",
        )
        await state.clear()
    else:
        await state.update_data(done=done, correct=correct)
        await callback.message.answer(feedback, parse_mode="HTML")
        await send_question(
            callback.bot, callback.message.chat.id, state, callback.from_user.id
        )

    await callback.answer()