import os
import logging
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Token bot tidak ditemukan! Pastikan BOT_TOKEN diset di .env")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Cari Teman 🔍")],
        [KeyboardButton(text="Next 🔁"), KeyboardButton(text="Berhenti ❌")]
    ],
    resize_keyboard=True
)

gender_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Cowo"), KeyboardButton(text="Cewe")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

waiting_users = set()
active_chats = {}
user_data = {}

class Form(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_photo = State()
    waiting_for_gender = State()
    waiting_for_about = State()

def find_partner(user_id):
    for partner_id in list(waiting_users):
        if partner_id != user_id:
            waiting_users.remove(partner_id)
            active_chats[user_id] = partner_id
            active_chats[partner_id] = user_id
            return partner_id
    waiting_users.add(user_id)
    return None

def end_chat(user_id):
    partner = active_chats.pop(user_id, None)
    if partner:
        active_chats.pop(partner, None)
    return partner

def is_chatting(user_id):
    return user_id in active_chats

def get_partner(user_id):
    return active_chats.get(user_id)

def set_user_info(user_id, name, age, photo):
    user_data[user_id] = {'name': name, 'age': age, 'photo': photo}

def get_user_info(user_id):
    data = user_data.get(user_id, {})
    return {
        'name': data.get('name', 'Anonim'),
        'age': data.get('age', 'Tidak diketahui'),
        'photo': data.get('photo'),
        'gender': data.get('gender', 'Tidak diketahui'),
        'about': data.get('about', 'Tidak tersedia')
    }

@router.message(Command("start"))
async def start_handler(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id
    if user_id not in user_data or not all(k in user_data[user_id] for k in ('name', 'age', 'photo', 'gender', 'about')):
        await msg.answer("👋 Halo! Sebelum mulai ngobrol, isi dulu data kamu ya🥰.", reply_markup=ReplyKeyboardRemove())
        await msg.answer("Ketik nama kamu:")
        await state.set_state(Form.waiting_for_name)
    else:
        await msg.answer("👋 Halo! Tekan *Cari Teman 🔍* untuk mulai ngobrol!", parse_mode="Markdown", reply_markup=main_kb)

@router.message(Form.waiting_for_name)
async def process_name(msg: types.Message, state: FSMContext):
    name = msg.text.strip()
    if not name.replace(" ", "").isalpha():
        await msg.answer("❌ Nama hanya boleh huruf. Coba lagi:")
        return
    if len(name) > 20:
        await msg.answer("❌ Nama terlalu panjang. Maksimal 20 karakter:")
        return
    await state.update_data(name=name)
    await msg.answer("Berapa umur kamu?")
    await
