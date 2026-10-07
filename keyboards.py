from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_list_kb(rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"❌ {en} — {ru}", callback_data=f"del|{wid}")]
            for wid, en, ru in rows
        ]
    )