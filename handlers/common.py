from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

router = Router()


@router.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет! Команды:\n"
        "/add — добавить одно слово\n"
        "/add_many — добавить сразу список\n"
        "/list — показать и удалить слова\n"
        "/exercise — упражнение\n"
        "/cancel — отменить текущий ввод"
    )


@router.message(Command("cancel"))
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.")


"""
Command Фильтр что сообщение является коммандной 
"""