from aiogram import Dispatcher
from . import common, words, exercises


def register_handlers(dp: Dispatcher):
    dp.include_router(common.router)
    dp.include_router(words.router)
    dp.include_router(exercises.router)