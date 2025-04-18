import os
import logging
import asyncio
import re
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

def set_user_info(user_id, name, age, photo, gender, about):
    user_data[user_id] = {
        'name': name,
        'age': age,
        'photo': photo,
        'gender': gender,
        'about': about
    }

def get_user_info(user_id):
    data = user_data.get(user_id, {})
    return {
        'name': data.get('name', 'Anonim'),
        'age': data.get('age', 'Tidak diketahui'),
        'photo': data.get('photo'),
        'gender': data.get('gender', 'Tidak diketahui'),
        'about': data.get('about', 'Tidak ada info')
    }

@router.message(Command("start"))
async def start_handler(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id
    if user_id not in user_data:
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
    await state.set_state(Form.waiting_for_age)

@router.message(Form.waiting_for_age)
async def process_age(msg: types.Message, state: FSMContext):
    age = msg.text.strip()
    if not age.isdigit() or not (1 <= int(age) <= 99):
        await msg.answer("❌ Umur harus angka dan maksimal 2 digit (1-99). Coba lagi:")
        return
    await state.update_data(age=age)
    await msg.answer("Sekarang kirim foto profil kamu:")
    await state.set_state(Form.waiting_for_photo)

@router.message(Form.waiting_for_photo, F.photo)
async def process_photo(msg: types.Message, state: FSMContext):
    photo_id = msg.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await msg.answer("Sekarang pilih gender kamu:", reply_markup=gender_kb)
    await state.set_state(Form.waiting_for_gender)

@router.message(Form.waiting_for_gender, F.text.in_(["Cowo", "Cewe"]))
async def process_gender(msg: types.Message, state: FSMContext):
    await state.update_data(gender=msg.text)
    await msg.answer("Tulis sesuatu tentang kamu (About Me):")
    await state.set_state(Form.waiting_for_about)

@router.message(Form.waiting_for_about)
async def process_about(msg: types.Message, state: FSMContext):
    about = msg.text.strip()
    if not re.fullmatch(r"[A-Za-z0-9\s.,!?()'-]{1,200}", about):
        await msg.answer("❌ Hanya huruf, angka, dan spasi yang diperbolehkan (maks 200 karakter). Coba lagi:")
        return
    data = await state.get_data()
    set_user_info(
        msg.from_user.id,
        name=data['name'],
        age=data['age'],
        photo=data['photo'],
        gender=data['gender'],
        about=about
    )
    await msg.answer(f"✅ Data kamu disimpan!\nNama: {data['name']}\nUmur: {data['age']}\nGender: {data['gender']}", reply_markup=main_kb)
    await state.clear()

@router.message(F.text == "Cari Teman 🔍")
async def cari_handler(msg: types.Message):
    user_id = msg.from_user.id
    if not all(k in user_data.get(user_id, {}) for k in ('name', 'age', 'photo', 'gender', 'about')):
        await msg.answer("❗ Isi data lengkap dulu dengan perintah /start.")
        return
    if is_chatting(user_id):
        await msg.answer("⚠️ Kamu sedang ngobrol. Tekan 'Next 🔁' untuk ganti teman.")
        return
    partner_id = find_partner(user_id)
    if partner_id:
        info_you = get_user_info(user_id)
        info_partner = get_user_info(partner_id)

        message_you = f"Nama: {info_you['name']}\nUmur: {info_you['age']}\nGender: {info_you['gender']}\nAbout: {info_you['about']}"
        message_partner = f"Nama: {info_partner['name']}\nUmur: {info_partner['age']}\nGender: {info_partner['gender']}\nAbout: {info_partner['about']}"

        await msg.answer(f"🔗 Terhubung dengan Teman ({info_partner['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(msg.chat.id, info_partner['photo'], caption=message_partner)
        
        await bot.send_message(partner_id, f"🔗 Terhubung dengan Teman ({info_you['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(partner_id, info_you['photo'], caption=message_you)
    else:
        await msg.answer("⏳ Menunggu teman tersedia...")

@router.message(F.text == "Next 🔁")
async def next_handler(msg: types.Message):
    user_id = msg.from_user.id
    partner = end_chat(user_id)
    if partner:
        await bot.send_message(partner, "🚫 Temanmu meninggalkan obrolan.", reply_markup=main_kb)
    new_partner = find_partner(user_id)
    if new_partner:
        info_you = get_user_info(user_id)
        info_partner = get_user_info(new_partner)

        message_you = f"Nama: {info_you['name']}\nUmur: {info_you['age']}\nGender: {info_you['gender']}\nAbout: {info_you['about']}"
        message_partner = f"Nama: {info_partner['name']}\nUmur: {info_partner['age']}\nGender: {info_partner['gender']}\nAbout: {info_partner['about']}"

        await msg.answer(f"🔄 Terhubung dengan Teman ({info_partner['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(msg.chat.id, info_partner['photo'], caption=message_partner)
        
        await bot.send_message(new_partner, f"🔄 Terhubung dengan Teman ({info_you['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(new_partner, info_you['photo'], caption=message_you)
    else:
        await msg.answer("⏳ Menunggu teman baru...")

@router.message(F.text == "Berh
