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
    keyboard=[[KeyboardButton(text="Cowo"), KeyboardButton(text="Cewe")]],
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
        'about': data.get('about', '-')
    }

@router.message(Command("start"))
async def start_handler(msg: types.Message, state: FSMContext):
    await msg.answer("👋 Halo! Sebelum mulai, isi dulu data kamu ya.", reply_markup=ReplyKeyboardRemove())
    await msg.answer("Ketik nama kamu:")
    await state.set_state(Form.waiting_for_name)

@router.message(Form.waiting_for_name)
async def process_name(msg: types.Message, state: FSMContext):
    name = msg.text.strip()
    if not name.replace(" ", "").isalpha():
        await msg.answer("❌ Nama hanya boleh huruf. Coba lagi:")
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
    await msg.answer("Pilih gender kamu:", reply_markup=gender_kb)
    await state.set_state(Form.waiting_for_gender)

@router.message(Form.waiting_for_gender, F.text.in_(["Cowo", "Cewe"]))
async def process_gender(msg: types.Message, state: FSMContext):
    await state.update_data(gender=msg.text)
    await msg.answer("Tulis sedikit tentang kamu (About Me):")
    await state.set_state(Form.waiting_for_about)

@router.message(Form.waiting_for_about)
async def process_about(msg: types.Message, state: FSMContext):
    about = msg.text.strip()
    if not all(c.isalnum() or c.isspace() for c in about):
        await msg.answer("❌ Hanya huruf, angka, dan spasi yang diperbolehkan. Coba lagi:")
        return

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
        reply_markup=main_kb
    )
    await state.clear()

@router.message(F.text == "Cari Teman 🔍")
async def cari_handler(msg: types.Message):
    user_id = msg.from_user.id
    if not all(k in user_data.get(user_id, {}) for k in ('name', 'age', 'photo', 'gender', 'about')):
        await msg.answer("❗ Data kamu belum lengkap. Ketik /start untuk isi.")
        return
    if is_chatting(user_id):
        await msg.answer("⚠️ Kamu sedang ngobrol. Gunakan 'Next 🔁' jika ingin ganti.")
        return

    partner_id = find_partner(user_id)
    if partner_id:
        info_you = get_user_info(user_id)
        info_partner = get_user_info(partner_id)

        caption = lambda u: (
            f"Nama: {u['name']}\nUmur: {u['age']}\nGender: {u['gender']}\nAbout: {u['about']}"
        )

        await msg.answer("🔗 Terhubung dengan seseorang!")
        await bot.send_photo(user_id, info_partner['photo'], caption=caption(info_partner))

        await bot.send_message(partner_id, "🔗 Terhubung dengan seseorang!")
        await bot.send_photo(partner_id, info_you['photo'], caption=caption(info_you))
    else:
        await msg.answer("⏳ Menunggu teman tersedia...")

@router.message(F.text == "Next 🔁")
async def next_handler(msg: types.Message):
    user_id = msg.from_user.id
    partner = end_chat(user_id)
    if partner:
        await bot.send_message(partner, "🚫 Temanmu meninggalkan obrolan.", reply_markup=main_kb)

    await cari_handler(msg)

@router.message(F.text == "Berhenti ❌")
async def stop_handler(msg: types.Message):
    partner = end_chat(msg.from_user.id)
    if partner:
        await bot.send_message(partner, "🚫 Temanmu keluar dari obrolan.", reply_markup=main_kb)
    await msg.answer("🚪 Kamu keluar dari obrolan.", reply_markup=main_kb)

@router.message(F.text)
async def chat_handler(msg: types.Message):
    user_id = msg.from_user.id
    if is_chatting(user_id):
        partner = get_partner(user_id)
        await bot.send_message(partner, msg.text)

@router.message(F.photo)
async def relay_photo(msg: types.Message):
    if is_chatting(msg.from_user.id):
        partner = get_partner(msg.from_user.id)
        await bot.send_photo(partner, msg.photo[-1].file_id, caption=msg.caption)

@router.message(F.sticker)
async def relay_sticker(msg: types.Message):
    if is_chatting(msg.from_user.id):
        partner = get_partner(msg.from_user.id)
        await bot.send_sticker(partner, msg.sticker.file_id)

@router.message(F.animation)
async def relay_gif(msg: types.Message):
    if is_chatting(msg.from_user.id):
        partner = get_partner(msg.from_user.id)
        await bot.send_animation(partner, msg.animation.file_id, caption=msg.caption)

@router.message(F.video)
async def relay_video(msg: types.Message):
    if is_chatting(msg.from_user.id):
        partner = get_partner(msg.from_user.id)
        await bot.send_video(partner, msg.video.file_id, caption=msg.caption)

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
