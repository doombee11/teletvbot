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
    waiting_users.discard(user_id)
    
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
    user_data[user_id] = {'name': name, 'age': age, 'photo': photo, 'gender': gender, 'about': about}
    logging.info(f"User data updated: {user_data[user_id]}")

def get_user_info(user_id):
    data = user_data.get(user_id, {})
    return {
        'name': data.get('name', 'Anonim'),
        'age': data.get('age', 'Tidak diketahui'),
        'photo': data.get('photo'),
        'gender': data.get('gender', 'Tidak diketahui'),
        'about': data.get('about', '-')
    }

@router.message(Command("start"))
async def start_handler(msg: types.Message, state: FSMContext):
    logging.info(f"User {msg.from_user.id} started the bot.")
    user_id = msg.from_user.id
    data = user_data.get(user_id)

    if data and all(k in data for k in ('name', 'age', 'photo', 'gender', 'about')):
        await msg.answer("👋 Selamat datang kembali!", reply_markup=main_kb)
        return

    await msg.answer("👋 Halo! Sebelum mulai, isi dulu data kamu ya.", reply_markup=ReplyKeyboardRemove())
    await msg.answer("Ketik nama kamu:")
    await state.set_state(Form.waiting_for_name)

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
        await msg.answer("❌ Umur harus angka 1–99. Coba lagi:")
        return
    await state.update_data(age=age)
    await msg.answer("Kirim foto profil kamu:")
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
    await msg.answer("Tulis sedikit tentang kamu (About Me):")
    await state.set_state(Form.waiting_for_about)

@router.message(Form.waiting_for_about)
async def process_about(msg: types.Message, state: FSMContext):
    about = msg.text.strip()

    if not re.match(r'^[A-Za-z0-9\s\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U0001FB00-\U0001FBFF\U0001FC00-\U0001FCFF\U0001FD00-\U0001FDFF\U0001FE00-\U0001FEFF\U0001FF00-\U0001FFFF]+$', about):
        await msg.answer("❌ Hanya huruf, angka, spasi, dan emotikon yang diperbolehkan. Coba lagi:")
        return

    about = about.replace('_', '\\_')

    data = await state.get_data()
    set_user_info(
        user_id=msg.from_user.id,
        name=data['name'],
        age=data['age'],
        photo=data['photo'],
        gender=data['gender'],
        about=about
    )

    await msg.answer(
        f"✅ Data kamu disimpan!\nNama: {data['name']}\nUmur: {data['age']}\nGender: {data['gender']}\nAbout: {about}",
        reply_markup=main_kb,
        parse_mode='Markdown'
    )
    await state.clear()

@router.message(F.voice)
async def handle_voice_note(msg: types.Message):
    user_id = msg.from_user.id

    if not is_chatting(user_id):
        await msg.answer("⚠️ Kamu belum terhubung dengan teman. Cari teman terlebih dahulu dengan 'Cari Teman 🔍'.")
        return

    partner_id = get_partner(user_id)

    if partner_id:
        try:
            await bot.send_voice(partner_id, msg.voice.file_id)
            await msg.answer("🎧 Voice note diteruskan ke teman kamu!")
        except Exception as e:
            logging.error(f"Failed to send voice note: {e}")
            await msg.answer("❌ Gagal mengirim voice note ke teman.")
    else:
        await msg.answer("⚠️ Teman chat kamu sudah keluar atau tidak tersedia.")

@router.message(F.text == "Cari Teman 🔍")
async def cari_handler(msg: types.Message):
    user_id = msg.from_user.id
    if not all(k in user_data.get(user_id, {}) for k in ('name', 'age', 'photo', 'gender', 'about')):
        await msg.answer("❗ Lengkapi dulu data kamu dengan /start.")
        return
    if is_chatting(user_id):
        await msg.answer("⚠️ Kamu sedang ngobrol. Tekan 'Next 🔁' untuk ganti teman.")
        return

    partner_id = find_partner(user_id)
    if partner_id:
        info_you = get_user_info(user_id)
        info_partner = get_user_info(partner_id)

        caption_partner = (
            f"Nama: {info_partner['name']}\n"
            f"Umur: {info_partner['age']}\n"
            f"Gender: {info_partner['gender']}\n"
            f"About: {info_partner['about']}"
        )

        caption_you = (
            f"Nama: {info_you['name']}\n"
            f"Umur: {info_you['age']}\n"
            f"Gender: {info_you['gender']}\n"
            f"About: {info_you['about']}"
        )

        await msg.answer(f"🔗 Terhubung dengan Teman ({info_partner['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(msg.chat.id, info_partner['photo'], caption=caption_partner)

        await bot.send_message(partner_id, f"🔗 Terhubung dengan Teman ({info_you['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(partner_id, info_you['photo'], caption=caption_you)
    else:
        await msg.answer("⏳ Menunggu teman baru...")

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

        caption_partner = (
            f"Nama: {info_partner['name']}\n"
            f"Umur: {info_partner['age']}\n"
            f"Gender: {info_partner['gender']}\n"
            f"About: {info_partner['about']}"
        )

        caption_you = (
            f"Nama: {info_you['name']}\n"
            f"Umur: {info_you['age']}\n"
            f"Gender: {info_you['gender']}\n"
            f"About: {info_you['about']}"
        )

        await msg.answer(f"🔄 Terhubung dengan Teman ({info_partner['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(msg.chat.id, info_partner['photo'], caption=caption_partner)

        await bot.send_message(new_partner, f"🔄 Terhubung dengan Teman ({info_you['age']} tahun)", parse_mode="Markdown")
        await bot.send_photo(new_partner, info_you['photo'], caption=caption_you)
    else:
        await msg.answer("⏳ Menunggu teman tersedia...")

@router.message(F.text == "Berhenti ❌")
async def stop_handler(msg: types.Message):
    partner = end_chat(msg.from_user.id)
    if partner:
        await bot.send_message(partner, "🚫 Temanmu keluar dari obrolan.", reply_markup=main_kb)
    await msg.answer("🚪 Kamu keluar dari obrolan.", reply_markup=main_kb)

@router.message(F.text)
async def relay_text_message(msg: types.Message):
    user_id = msg.from_user.id

    if not is_chatting(user_id):
        await msg.answer("⚠️ Kamu belum terhubung dengan teman. Cari teman dulu dengan 'Cari Teman 🔍'.")
        return

    partner_id = get_partner(user_id)

    if partner_id:
        try:
            await bot.send_message(partner_id, msg.text)
        except Exception as e:
            logging.error(f"Gagal kirim pesan ke partner: {e}")
            await msg.answer("❌ Gagal mengirim pesan ke teman.")
    else:
        await msg.answer("⚠️ Teman kamu sudah keluar atau tidak tersedia.")

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
