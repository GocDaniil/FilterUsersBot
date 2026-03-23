import io
import os
import asyncio
import random
import sqlite3
import string
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Filter, StateFilter, Command

router = Router()

@router.message(Command(commands=["start"]))
async def kb_manager(msg: types.Message):

    kb = InlineKeyboardMarkup(
        inline_keyboard = [
            [InlineKeyboardButton(text="Перемешать", callback_data="shuffle")],
            [InlineKeyboardButton(text="Удалить дубликаты", callback_data="rem_dublicates")],
            [InlineKeyboardButton(text="Запомнить логины", callback_data="save")],
            [InlineKeyboardButton(text="Создать логины", callback_data="create")]
        ])

    await msg.answer("Выберите действие", reply_markup=kb)

@router.callback_query(F.data == "create")
async def create(call: CallbackQuery):

    chars = string.ascii_letters + string.digits
    logins = []

    for i in range(100):
        random.seed(os.urandom(16), version=2)
        length = random.randint(8, 20)

        login = ''.join(random.choices(chars, k=length))
        logins.append(login)

    text = "\n".join(logins)
    bytes = text.encode("utf-8")

    file = BufferedInputFile(bytes, filename="logins.txt")

    await call.message.answer_document(document=file, caption="Созданы уникальные логины")
    await call.answer()

@router.callback_query(F.data != "create")
async def waiting_file(call: CallbackQuery, state: FSMContext):

    await state.set_state("waiting_for_file")
    await state.update_data(action=call.data)
    await call.answer("Отправьте файл с логинами")

@router.message(F.document, StateFilter("waiting_for_file"))
async def file(msg: types.Message, state: FSMContext, bot: Bot):

    data = await state.get_data()
    action = data.get("action")

    await state.clear()

    if not msg.document:
        msg.answer("Это не документ")
        return

    path = await bot.get_file(msg.document.file_id)

    bio: io.BytesIO = await bot.download_file(path.file_path)
    bio.seek(0)

    if action == "shuffle":
        await shuffle(bio, msg)

    elif action == "rem_dublicates":
        await rem_dublicates(bio, msg)

    elif action == "save":
        await save(bio, msg)

async def shuffle(bio: io.BytesIO, msg: types.Message):

    content = bio.read()
    text = content.decode("utf-8")
    lines = text.splitlines()

    random.seed(os.urandom(16), version=2)
    random.shuffle(lines)

    new_text = "\n".join(lines)
    bytes = new_text.encode("utf-8")
    file = BufferedInputFile(bytes, msg.document.file_name)

    await msg.answer_document(document=file, filename=msg.document.file_name, caption="Файл перемешан!")

async def rem_dublicates(bio: io.BytesIO, msg:types.Message):

    content = bio.read()
    text = content.decode("utf-8")
    lines = text.splitlines()

    seen = {}
    result = []

    for line in lines:
        if line not in seen:
            seen[line] = True
            result.append(line)

    new_text = "\n".join(result)
    bytes = new_text.encode("utf-8")
    file = BufferedInputFile(bytes, msg.document.file_name)

    await msg.answer_document(document=file, filename=msg.document.file_name, caption="Дубликаты удалены")

async def save(bio: io.BytesIO, msg: types.Message):

    content = bio.read()
    text = content.decode("utf-8")
    lines = text.splitlines()

    conn = sqlite3.connect("logins.db")

    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS logins(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    login TEXT NOT NULL)
                    """)

    data = [(line,) for line in lines if line]

    cur.executemany("""INSERT INTO logins(login) VALUES (?)""", data)

    conn.commit()
    conn.close()

    await msg.answer("Файл сохранен в БД")

async def main():
    bot = Bot(token="8710935577:AAEhJkOyFZc1bNsOqLSZBNazTNdbGi1Mw1k")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
    