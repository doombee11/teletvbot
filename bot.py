from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import logging

TOKEN = os.getenv("7501460896:AAHImKheBZRP-ckVD1IVlnq868hnUhvi0q4")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(KeyboardButton("Cari Teman 🔍"))
main_kb.add(KeyboardButton("Next 🔁"), KeyboardButton("Berhenti ❌"))

gender_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
gender_kb.add(KeyboardButton("Pria"), KeyboardButton("Wanita"))

waiting_users = set()
active_chats = {}
user_data = {}

class Form(StatesGroup):
    waiting_for_name = State()  # State untuk menunggu nama

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

def set_gender(user_id, gender):
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['gender'] = gender

def set_nama(user_id, nama):
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['nama'] = nama

def get_user_info(user_id):
    return user_data.get(user_id, {'gender': 'Tidak diketahui', 'nama': 'Anonim'})

@dp.message_handler(commands=['start'])
async def start_handler(msg: types.Message):
    await msg.answer(
        "👋 Halo! Ini bot Random Chat ala OmeTV versi chat teks.\n\n"
        "Kamu bisa:\n"
        "🔹 /gender - atur gender kamu\n"
        "🔹 /setnama - atur nama panggilan\n\n"
        "Lalu tekan *Cari Teman 🔍* buat mulai ngobrol!",
        parse_mode="Markdown", reply_markup=main_kb
    )

@dp.message_handler(commands=['gender'])
async def gender_handler(msg: types.Message):
    await msg.answer("Pilih gender kamu:", reply_markup=gender_kb)

@dp.message_handler(lambda msg: msg.text in ["Pria", "Wanita"])
async def set_gender_handler(msg: types.Message):
    set_gender(msg.from_user.id, msg.text)
    await msg.answer(f"Gender kamu diset sebagai *{msg.text}*", parse_mode='Markdown', reply_markup=main_kb)

@dp.message_handler(commands=['setnama'])
async def set_nama_handler(msg: types.Message):
    await msg.answer("Ketik nama panggilan kamu (maks 20 karakter):", reply_markup=ReplyKeyboardRemove())
    await Form.waiting_for_name.set()  # Pindah ke state waiting_for_name

@dp.message_handler(state=Form.waiting_for_name)
async def process_name(msg: types.Message, state: FSMContext):
    name = msg.text
    if len(name) > 20:
        await msg.answer("Nama terlalu panjang. Coba lagi (maks 20 karakter):")
        return
    set_nama(msg.from_user.id, name)
    await msg.answer(f"Nama kamu diset sebagai *{name}*", parse_mode="Markdown", reply_markup=main_kb)
    await state.finish()  # Kembalikan ke state awal

@dp.message_handler(lambda msg: msg.text == "Cari Teman 🔍")
async def cari_handler(msg: types.Message):
    user_id = msg.from_user.id
    if is_chatting(user_id):
        await msg.answer("⚠️ Kamu sedang ngobrol. Tekan 'Next 🔁' untuk ganti teman.")
        return

    partner_id = find_partner(user_id)
    if partner_id:
        info_partner = get_user_info(partner_id)
        info_you = get_user_info(user_id)

        await msg.answer(f"🔗 Terhubung dengan *{info_partner['nama']}* ({info_partner['gender']})", parse_mode="Markdown")
        await bot.send_message(partner_id, f"🔗 Terhubung dengan *{info_you['nama']}* ({info_you['gender']})", parse_mode="Markdown")
    else:
        await msg.answer("⏳ Menunggu teman tersedia...")

@dp.message_handler(lambda msg: msg.text == "Berhenti ❌")
async def stop_handler(msg: types.Message):
    user_id = msg.from_user.id
    partner = end_chat(user_id)
    if partner:
        await bot.send_message(partner, "🚫 Temanmu telah keluar dari obrolan.")
    await msg.answer("Kamu telah keluar dari obrolan.", reply_markup=main_kb)

@dp.message_handler(lambda msg: msg.text == "Next 🔁")
async def next_handler(msg: types.Message):
    user_id = msg.from_user.id
    partner = end_chat(user_id)
    if partner:
        await bot.send_message(partner, "🚫 Temanmu meninggalkan obrolan.")
    new_partner = find_partner(user_id)
    if new_partner:
        info_partner = get_user_info(new_partner)
        info_you = get_user_info(user_id)

        await msg.answer(f"🔄 Terhubung dengan *{info_partner['nama']}* ({info_partner['gender']})", parse_mode="Markdown")
        await bot.send_message(new_partner, f"🔄 Terhubung dengan *{info_you['nama']}* ({info_you['gender']})", parse_mode="Markdown")
    else:
        await msg.answer("⏳ Menunggu teman baru...")

@dp.message_handler()
async def chat_handler(msg: types.Message):
    user_id = msg.from_user.id
    if is_chatting(user_id):
        partner = get_partner(user_id)
        await bot.send_message(partner, msg.text)
    else:
        await msg.answer("Kamu belum terhubung dengan siapa pun.\nTekan *Cari Teman 🔍* untuk mulai.", parse_mode="Markdown")

if __name__ == '__main__':
    dp.start_polling()
