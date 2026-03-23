import io
import os
import aiohttp
import asyncio
import random
import sqlite3
import string
from io import BytesIO
from maxapi import Bot, Dispatcher, Router, types, F
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types.attachments.buttons import CallbackButton
from maxapi.types.input_media import InputMediaBuffer
from maxapi.types import MessageCreated, Command
from maxapi.types.attachments import File
from maxapi.context import MemoryContext, StatesGroup, State
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.enums.upload_type import UploadType

router = Router()
bot = Bot(token="")
dp = Dispatcher(storage=MemoryContext)

class Action(CallbackPayload, prefix='action'):
    type: str

class Form(StatesGroup):
    waiting_file = State()

@dp.message_created(Command('start'))
async def kb_manager(ev: MessageCreated):

    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Перемешать", payload=Action(type="shuffle").pack()),
        CallbackButton(text="Удалить дубликаты", payload=Action(type="rem_dublicates").pack()),
        CallbackButton(text="Запомнить логины", payload=Action(type="save").pack()),
        CallbackButton(text="Создать логины", payload=Action(type="create").pack())
    )

    await ev.message.answer(text="Выберите действие", attachments=[builder.as_markup()])

@dp.message_callback(Action.filter(F.type == "create"))
async def create(payload: Action, ev: MessageCreated):

    chars = string.ascii_letters + string.digits
    logins = []

    for i in range(100):
        random.seed(os.urandom(16), version=2)
        length = random.randint(8, 20)

        login = ''.join(random.choices(chars, k=length))
        logins.append(login)

    text = "\n".join(logins)
    bytes = text.encode("utf-8")

    file = InputMediaBuffer(buffer=bytes, filename="logins.txt", type=UploadType.FILE)

    await ev.message.answer(text="Созданы уникальные логины", attachments=file)

@dp.message_created(F.message.body.attachment)
async def waiting_file(payload: Action, ev: MessageCreated, context: MemoryContext):

    await context.set_state(Form.waiting_file)
    await context.update_data(payload=payload)
    await ev.message.answer(text="Отправьте файл с логинами")

@dp.message_created(Form.waiting_file)
async def file(ev: MessageCreated, context: MemoryContext):

    data = await context.get_data()
    action = await data.get("action")

    msg = ev.message
    attachments = msg.body.attachments

    if attachments != UploadType.FILE:
        await msg.answer(text="Это не документ")
        return

    url = attachments.payload.url
    token = attachments.payload.token

    headers = {"Authorization": f"Bearer {token}"} if token else None

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:

            resp.raise_for_status()

            bio: io.BytesIO = BytesIO(await resp.read())
            name = bio.name
            text = bio.read().decode("utf-8")
            bio.seek(0)

    if action == "shuffle":
        await shuffle(text, msg, name)

    elif action == "rem_dublicates":
        await rem_dublicates(text, msg, name)

    elif action == "save":
        await save(text, msg, name)

    await context.clear()

async def shuffle(text: str, msg, name):

    lines = text.splitlines()

    random.seed(os.urandom(16), version=2)
    random.shuffle(lines)

    new_text = "\n".join(lines)
    bytes = new_text.encode("utf-8")
    file = InputMediaBuffer(buffer=bytes, filename=name, type=UploadType.FILE)

    await msg.answer(text="Файл перемеша!", attachments=file)

async def rem_dublicates(text: str, msg, name):

    lines = text.splitlines()

    seen = {}
    result = []

    for line in lines:
        if line not in seen:
            seen[line] = True
            result.append(line)

    new_text = "\n".join(result)
    bytes = new_text.encode("utf-8")
    file = InputMediaBuffer(buffer=bytes, filename=name, type=UploadType.FILE)

    await msg.answer(text="Дубликаты удалены", attachments=file)

async def save(text: str, msg, name):

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
    await dp.include_routers(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

