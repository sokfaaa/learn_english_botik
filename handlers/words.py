from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from handlers.examples import prefetch_examples
from asyncio import create_task
from states import AddWord
from utils import parse_bulk
from keyboards import build_list_kb
from database import (
    add_word,
    get_words_with_ids,
    delete_word,
)

router = Router()


# ---------- Добавление одного слова ----------

@router.message(Command("add"))
async def add_start(message: types.Message, state: FSMContext):
    await message.answer("Введи английское слово:")
    await state.set_state(AddWord.waiting_en)


@router.message(AddWord.waiting_en)
async def add_en(message: types.Message, state: FSMContext):
    await state.update_data(en=message.text.strip().lower())
    await message.answer("Введи перевод:")
    await state.set_state(AddWord.waiting_ru)

@router.message(AddWord.waiting_ru)
async def add_ru(message: types.Message, state: FSMContext):
    data = await state.get_data()
    en = data["en"]
    ru = message.text.strip().lower()

    inserted = await add_word(message.from_user.id, en, ru)

    if inserted:
        await message.answer(f"Добавлено: {en} — {ru}")
        # 👇 прогреваем пример в фоне
        create_task(prefetch_examples([en]))
    else:
        await message.answer(f"Слово «{en}» уже есть в списке.")
    await state.clear()


# ---------- Массовое добавление ----------

@router.message(Command("add_many"))
async def add_many_start(message: types.Message, state: FSMContext):
    await message.answer(
        "Отправь список в формате:\n"
        "<code>слово:перевод; слово2:перевод2</code>\n\n"
        "Например:\n"
        "<code>apple:яблоко; dog:собака; cat:кошка</code>",
        parse_mode="HTML",
    )
    await state.set_state(AddWord.waiting_many)


@router.message(AddWord.waiting_many)
async def add_many_process(message: types.Message, state: FSMContext):
    pairs, errors = parse_bulk(message.text)

    if not pairs:
        await message.answer(
            "Не смог распознать ни одной пары. Формат: <code>слово:перевод; слово2:перевод2</code>\n"
            "Попробуй ещё раз или /cancel",
            parse_mode="HTML",
        )
        return

    added = 0
    skipped = 0
    added_words = []

    for en, ru in pairs:
        inserted = await add_word(message.from_user.id, en, ru)

        if inserted:
            added += 1
            added_words.append(en)
        else:
            skipped += 1

    if added_words:
        create_task(prefetch_examples(added_words))

    report = f"✅ Добавлено: {added}\n♻️ Уже было: {skipped}"
    if errors:
        report += f"\n⚠️ Не распознано: {len(errors)} — {', '.join(errors[:5])}"
        if len(errors) > 5:
            report += " …"

    await message.answer(report)
    await state.clear()


# ---------- Список + удаление ----------

@router.message(Command("list"))
async def list_words(message: types.Message):
    rows = await get_words_with_ids(message.from_user.id)
    if not rows:
        await message.answer("Список пуст. Добавь слова через /add или /add_many")
        return

    await message.answer(
        f"Твои слова ({len(rows)}). Нажми ❌, чтобы удалить:",
        reply_markup=build_list_kb(rows),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("del|"))
async def delete_word_handler(callback: types.CallbackQuery):
    word_id = int(callback.data.split("|", 1)[1])
    await delete_word(word_id, callback.from_user.id)
    rows = await get_words_with_ids(callback.from_user.id)

    await callback.answer("Удалено")
    if not rows:
        await callback.message.edit_text("Список пуст. Добавь слова через /add или /add_many")
    else:
        await callback.message.edit_text(
            f"Твои слова ({len(rows)}). Нажми ❌, чтобы удалить:",
            reply_markup=build_list_kb(rows),
        )