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
    return user_data.get(user_id, {'name': 'Anonim', 'age': 'Tidak diketahui', 'photo': None})

def set_gender(user_id, gender):
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['gender'] = gender

@router.message(Command("start"))
async def start_handler(msg: types.Message):
    user_id = msg.from_user.id
    if user_id not in user_data or not all(k in user_data[user_id] for k in ('name', 'age', 'photo')):
        await msg.answer("👋 Halo! Sebelum mulai ngobrol, isi dulu data kamu ya: nama, umur, dan foto.", reply_markup=ReplyKeyboardRemove())
        await msg.answer("Ketik nama kamu (maks 20 karakter, huruf saja):")
        await Form.waiting_for_name.set()
    else:
        await msg.answer("👋 Halo! Tekan *Cari Teman 🔍* untuk mulai ngobrol!", parse_mode="Markdown", reply_markup=main_kb)

@router.message(Form.waiting_for_name)
async def process_name(msg: types.Message, state: FSMContext):
    name = msg.text.strip()
    if not name.isalpha():
        await msg.answer("❌ Nama hanya boleh huruf. Coba lagi:")
        return
    if len(name) > 20:
        await msg.answer("❌ Nama terlalu panjang. Maksimal 20 karakter:")
        return
    await state.update_data(name=name)
    await msg.answer("Berapa umur kamu? (angka 1-99):")
    await Form.waiting_for_age.set()

@router.message(Form.waiting_for_age)
async def process_age(msg: types.Message, state: FSMContext):
    age = msg.text.strip()
    if not age.isdigit() or not (1 <= int(age) <= 99):
        await msg.answer("❌ Umur harus angka dan maksimal 2 digit (1-99). Coba lagi:")
        return
    await state.update_data(age=age)
    await msg.answer("Sekarang kirim foto profil kamu:")
    await Form.waiting_for_photo.set()

@router.message(Form.waiting_for_photo, F.photo)
async def process_photo(msg: types.Message, state: FSMContext):
    photo_id = msg.photo[-1].file_id
    data = await state.get_data()
    set_user_info(msg.from_user.id, data['name'], data['age'], photo_id)
    await msg.answer(f"✅ Data kamu disimpan!\nNama: {data['name']}\nUmur: {data['age']}", reply_markup=main_kb)
    await state.clear()

@router.message(Command("gender"))
async def gender_handler(msg: types.Message):
    await msg.answer("Pilih gender kamu:", reply_markup=gender_kb)

@router.message(F.text.in_(["Pria", "Wanita"]))
async def set_gender_handler(msg: types.Message):
    set_gender(msg.from_user.id, msg.text)
    await msg.answer(f"Gender kamu diset sebagai *{msg.text}*", parse_mode="Markdown", reply_markup=main_kb)

@router.message(F.text == "Cari Teman 🔍")
async def cari_handler(msg: types.Message):
    user_id = msg.from_user.id
    if not all(k in user_data.get(user_id, {}) for k in ('name', 'age', 'photo')):
        await msg.answer("❗ Isi nama, umur, dan foto kamu dulu dengan perintah /start.")
        return
    if is_chatting(user_id):
        await msg.answer("⚠️ Kamu sedang ngobrol. Tekan 'Next 🔁' untuk ganti teman.")
        return
    partner_id = find_partner(user_id)
    if partner_id:
        info_you = get_user_info(user_id)
        info_partner = get_user_info(partner_id)
        await msg.answer(f"🔗 Terhubung dengan *{info_partner['name']}* ({info_partner['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(msg.chat.id, info_partner['photo'])
        await bot.send_message(partner_id, f"🔗 Terhubung dengan *{info_you['name']}* ({info_you['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(partner_id, info_you['photo'])
    else:
        await msg.answer("⏳ Menunggu teman tersedia...")

@router.message(F.text == "Berhenti ❌")
async def stop_handler(msg: types.Message):
    partner = end_chat(msg.from_user.id)
    if partner:
        await bot.send_message(partner, "🚫 Temanmu keluar dari obrolan.")
    await msg.answer("🚪 Kamu keluar dari obrolan.", reply_markup=main_kb)

@router.message(F.text == "Next 🔁")
async def next_handler(msg: types.Message):
    user_id = msg.from_user.id
    partner = end_chat(user_id)
    if partner:
        await bot.send_message(partner, "🚫 Temanmu meninggalkan obrolan.")
    new_partner = find_partner(user_id)
    if new_partner:
        info_you = get_user_info(user_id)
        info_partner = get_user_info(new_partner)
        await msg.answer(f"🔄 Terhubung dengan *{info_partner['name']}* ({info_partner['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(msg.chat.id, info_partner['photo'])
        await bot.send_message(new_partner, f"🔄 Terhubung dengan *{info_you['name']}* ({info_you['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(new_partner, info_you['photo'])
    else:
        await msg.answer("⏳ Menunggu teman baru...")

@router.message(F.text)
async def text_chat_handler(msg: types.Message):
    user_id = msg.from_user.id
    if is_chatting(user_id):
        partner = get_partner(user_id)
        await bot.send_message(partner, msg.text)
    else:
        await msg.answer("Kamu belum terhubung dengan siapa pun.\nTekan *Cari Teman 🔍* untuk mulai.", parse_mode="Markdown")

@router.message(F.photo)
async def photo_chat_handler(msg: types.Message):
    user_id = msg.from_user.id
    if is_chatting(user_id):
        partner = get_partner(user_id)
        await bot.send_photo(partner, msg.photo[-1].file_id, caption=msg.caption)
    else:
        await msg.answer("Kamu belum terhubung. Tekan *Cari Teman 🔍* untuk mulai.", parse_mode="Markdown")

@router.message(F.video)
async def video_chat_handler(msg: types.Message):
    user_id = msg.from_user.id
    if is_chatting(user_id):
        partner = get_partner(user_id)
        await bot.send_video(partner, msg.video.file_id, caption=msg.caption)
    else:
        await msg.answer("Kamu belum terhubung. Tekan *Cari Teman 🔍* untuk mulai.", parse_mode="Markdown")

async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
