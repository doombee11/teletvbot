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
    raise ValueError("Token bot tidak ditemukan! Pastikan environment variable BOT_TOKEN sudah diset.")

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
        [KeyboardButton(text="Pria"), KeyboardButton(text="Wanita")]
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

def find_partner(user_id):
    if waiting_users:
        partner_id = waiting_users.pop()
        if partner_id != user_id:
            active_chats[user_id] = partner_id
            active_chats[partner_id] = user_id
            return partner_id
        else:
            waiting_users.add(user_id)
            return None
    else:
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
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['name'] = name
    user_data[user_id]['age'] = age
    user_data[user_id]['photo'] = photo

def get_user_info(user_id):
    return user_data.get(user_id, {'name': 'Anonim', 'age': 'Tidak diketahui', 'photo': None})

@router.message(Command("start"))
async def start_handler(msg: types.Message):
    user_id = msg.from_user.id
    
    if user_id not in user_data:
        await msg.answer(
            "👋 Halo! Sebelum mulai ngobrol, kita perlu mengisi beberapa data. Yuk, isi nama, umur, dan foto kamu!",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
        )
        await msg.answer("Ketik nama kamu (maks 20 karakter):", reply_markup=ReplyKeyboardRemove())
        await Form.waiting_for_name.set()
    else:
        await msg.answer(
            "👋 Halo! Kamu sudah terdaftar. Tekan *Cari Teman 🔍* untuk mulai ngobrol!",
            parse_mode="Markdown", reply_markup=main_kb
        )

@router.message(Form.waiting_for_name)
async def process_name(msg: types.Message, state: FSMContext):
    name = msg.text
    if len(name) > 20:
        await msg.answer("Nama terlalu panjang. Coba lagi (maks 20 karakter):")
        return
    await state.update_data(name=name)
    await msg.answer("Berapa umur kamu?", reply_markup=ReplyKeyboardRemove())
    await Form.waiting_for_age.set()

@router.message(Form.waiting_for_age)
async def process_age(msg: types.Message, state: FSMContext):
    age = msg.text
    if not age.isdigit():
        await msg.answer("Umur harus berupa angka. Coba lagi:")
        return
    await state.update_data(age=age)
    await msg.answer("Kirimkan foto kamu:", reply_markup=ReplyKeyboardRemove())
    await Form.waiting_for_photo.set()

@router.message(Form.waiting_for_photo, content_types=types.ContentTypes.PHOTO)
async def process_photo(msg: types.Message, state: FSMContext):
    photo = msg.photo[-1].file_id
    user_data = await state.get_data()
    name = user_data.get("name")
    age = user_data.get("age")
    set_user_info(msg.from_user.id, name, age, photo)
    
    await msg.answer(f"Data kamu berhasil disimpan!\nNama: {name}\nUmur: {age}", reply_markup=main_kb)
    await state.clear()

@router.message(Command("gender"))
async def gender_handler(msg: types.Message):
    await msg.answer("Pilih gender kamu:", reply_markup=gender_kb)

@router.message(F.text.in_(["Pria", "Wanita"]))
async def set_gender_handler(msg: types.Message):
    set_gender(msg.from_user.id, msg.text)
    await msg.answer(f"Gender kamu diset sebagai *{msg.text}*", parse_mode='Markdown', reply_markup=main_kb)

@router.message(F.text == "Cari Teman 🔍")
async def cari_handler(msg: types.Message):
    user_id = msg.from_user.id
    if is_chatting(user_id):
        await msg.answer("⚠️ Kamu sedang ngobrol. Tekan 'Next 🔁' untuk ganti teman.")
        return

    partner_id = find_partner(user_id)
    if partner_id:
        info_partner = get_user_info(partner_id)
        info_you = get_user_info(user_id)

        partner_photo = info_partner['photo'] if info_partner['photo'] else None
        await msg.answer(
            f"🔗 Terhubung dengan *{info_partner['name']}* ({info_partner['age']} tahun)",
            parse_mode="Markdown"
        )
        await bot.send_message(partner_id, f"🔗 Terhubung dengan *{info_you['name']}* ({info_you['age']} tahun)", parse_mode="Markdown")
        if partner_photo:
            await bot.send_photo(msg.chat.id, partner_photo)
    else:
        await msg.answer("⏳ Menunggu teman tersedia...")

@router.message(F.text == "Berhenti ❌")
async def stop_handler(msg: types.Message):
    user_id = msg.from_user.id
    partner = end_chat(user_id)
    if partner:
        await bot.send_message(partner, "🚫 Temanmu telah keluar dari obrolan.")
    await msg.answer("Kamu telah keluar dari obrolan.", reply_markup=main_kb)

@router.message(F.text == "Next 🔁")
async def next_handler(msg: types.Message):
    user_id = msg.from_user.id
    partner = end_chat(user_id)
    if partner:
        await bot.send_message(partner, "🚫 Temanmu meninggalkan obrolan.")
    new_partner = find_partner(user_id)
    if new_partner:
        info_partner = get_user_info(new_partner)
        info_you = get_user_info(user_id)

        partner_photo = info_partner['photo'] if info_partner['photo'] else None
        await msg.answer(
            f"🔄 Terhubung dengan *{info_partner['name']}* ({info_partner['age']} tahun)",
            parse_mode="Markdown"
        )
        await bot.send_message(new_partner, f"🔄 Terhubung dengan *{info_you['name']}* ({info_you['age']} tahun)", parse_mode="Markdown")
        if partner_photo:
            await bot.send_photo(msg.chat.id, partner_photo)
    else:
        await msg.answer("⏳ Menunggu teman baru...")

@router.message(F.text)
async def chat_handler(msg: types.Message):
    user_id = msg.from_user.id
    if is_chatting(user_id):
        partner = get_partner(user_id)
        await bot.send_message(partner, msg.text)
    else:
        await msg.answer("Kamu belum terhubung dengan siapa pun.\nTekan *Cari Teman 🔍* untuk mulai.", parse_mode="Markdown")

@router.message(F.photo)
async def photo_handler(msg: types.Message):
    user_id = msg.from_user.id
    if is_chatting(user_id):
        partner = get_partner(user_id)
        await bot.send_photo(partner, msg.photo[-1].file_id, caption=msg.caption)
    else:
        await msg.answer("Kamu belum terhubung. Tekan *Cari Teman 🔍* untuk mulai.", parse_mode="Markdown")

@router.message(F.video)
async def video_handler(msg: types.Message):
    user_id = msg.from_user.id
    if is_chatting(user_id):
        partner = get_partner(user_id)
        await bot.send_video(partner, msg.video.file_id, caption=msg.caption)
    else:
        await msg.answer("Kamu belum terhubung. Tekan *Cari Teman 🔍*
