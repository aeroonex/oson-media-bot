import os
import asyncio
import json
import re
import subprocess
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from acrcloud.recognizer import ACRCloudRecognizer
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import (
    FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, InlineQuery, 
    InlineQueryResultAudio, InlineQueryResultCachedVideo
)
import aiohttp
import yt_dlp

TOKEN = '8653098410:AAHwizKs_I5ZpsPu7EGTm-rx0uKFi03u1co'
CHANNEL_ID = '@aeroonex'
ADMIN_ID = 5064451675

ACR_CONFIG = {
    'host': 'identify-ap-southeast-1.acrcloud.com',
    'access_key': '9b8e62b411f5ee17294159ef9e674576',
    'access_secret': 'lucigoAxfS1wM0gml5BbjWKMrOTSXMW3Ae6fcCmZ',
    'timeout': 15
}

BASE_DIR = '/var/www/shazam-app'
USERS_FILE = os.path.join(BASE_DIR, 'users.json')
FILE_CACHE_FILE = os.path.join(BASE_DIR, 'file_cache.json')
COOKIES_FILE = os.path.join(BASE_DIR, 'cookies.txt')

video_storage_cache = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(auto_clean_videos())
    polling_task = asyncio.create_task(dp.start_polling(bot))
    yield
    await dp.stop_polling()
    polling_task.cancel()

app = FastAPI(lifespan=lifespan)
session = AiohttpSession(timeout=120)
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()
recognizer = ACRCloudRecognizer(ACR_CONFIG)

app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

search_cache = {}
admin_state = {} 
user_states = {}

async def auto_clean_videos():
    while True:
        await asyncio.sleep(30)
        now = time.time()
        to_delete = []
        for file_path, timestamp in video_storage_cache.items():
            if now - timestamp > 300:
                to_delete.append(file_path)
                
        for file_path in to_delete:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                video_storage_cache.pop(file_path, None)
            except: pass

def load_users():
    if not os.path.exists(USERS_FILE): return {}
    try:
        with open(USERS_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_user(user_id, full_name, username, inviter_id=None):
    users = load_users()
    str_id = str(user_id)
    new_user = False
    
    if str_id not in users:
        users[str_id] = {
            'name': full_name or "Noma'lum",
            'username': f"@{username}" if username else "Mavjud emas",
            'balance': 0,
            'invited_by': None,
            'refs': 0,
            'favorites': [] 
        }
        new_user = True
        
    if inviter_id and str_id in users and not users[str_id].get('invited_by'):
        if str_id != str(inviter_id) and str_id != str(ADMIN_ID):
            users[str_id]['invited_by'] = inviter_id
            str_inviter = str(inviter_id)
            if str_inviter in users:
                users[str_inviter]['balance'] += 500
                users[str_inviter]['refs'] += 1
                
                asyncio.create_task(notify_user(int(inviter_id), f"🎉 <b>Yangi do'st qo'shildi!</b>\nSizga 500 so'm hisoblandi."))
                
                inviter_name = users[str_inviter].get('name', 'Noma\'lum')
                asyncio.create_task(notify_user(ADMIN_ID, 
                    f"🤝 <b>Yangi Referal!</b>\n"
                    f"👤 Kim qo'shildi: {escape_html(full_name)} (ID: <code>{user_id}</code>)\n"
                    f"🗣 Kim taklif qildi: {escape_html(inviter_name)} (ID: <code>{inviter_id}</code>)"
                ))
                new_user = True
                
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)
    return new_user

async def notify_user(chat_id, text):
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except: pass

def update_user_favorites(user_id, music_data):
    users = load_users()
    str_id = str(user_id)
    if str_id in users:
        if 'favorites' not in users[str_id]:
            users[str_id]['favorites'] = []
            
        if not any(f['title'] == music_data['title'] for f in users[str_id]['favorites']):
            users[str_id]['favorites'].append(music_data)
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f, indent=4)
            return True
    return False

def load_file_cache():
    if not os.path.exists(FILE_CACHE_FILE): return {}
    try:
        with open(FILE_CACHE_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_file_to_cache(key, file_id, file_type, extra_data=None):
    cache = load_file_cache()
    cache[key] = {
        'file_id': file_id,
        'type': file_type,
        'data': extra_data or {}
    }
    with open(FILE_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=4)

def get_main_keyboard():
    keyboard = [
        [KeyboardButton(text="🎵 Musiqa qidirish"), KeyboardButton(text="🤫 Anonim Xabar")],
        [KeyboardButton(text="💰 Pul ishlash"), KeyboardButton(text="❤️ Sevimlilar (/my)")],
        [KeyboardButton(text="💳 Kabinet")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_admin_keyboard():
    keyboard = [
        [KeyboardButton(text="📝 Foydalanuvchilarga xabar yuborish")],
        [KeyboardButton(text="👥 Foydalanuvchilar ro'yxati"), KeyboardButton(text="📊 Umumiy soni")],
        [KeyboardButton(text="🔙 Oddiy foydalanuvchi rejimiga qaytish")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_marketing_caption(title, artist):
    return (
        f"🎵 <b>Nomi:</b> {escape_html(title)}\n"
        f"👤 <b>Artist/Kanal:</b> {escape_html(artist)}\n\n"
        f"🚀 <i>Istagan musiqangizni tez va oson toping!</i>\n"
        f"🤖 <b>Botimiz:</b> @oson_mediabot"
    )

def get_clean_caption(title, artist):
    return (
        f"🎵 <b>Nomi:</b> {escape_html(title)}\n"
        f"👤 <b>Artist/Kanal:</b> {escape_html(artist)}"
    )

def get_share_keyboard(music_title, index=None, share_id=None):
    keyboard_layout = []
    if index is not None:
        keyboard_layout.append([
            InlineKeyboardButton(text="❤️ Sevimlilarga qo'shish", callback_data=f"like_{index}")
        ])
    if share_id:
        keyboard_layout.append([
            InlineKeyboardButton(text="🔗 Do'stlarga ulashish", switch_inline_query=share_id)
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard_layout)

async def check_subscription(user_id: int) -> bool:
    if user_id == ADMIN_ID: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

async def send_sub_alert(message: types.Message):
    sub_text = "⚠️ <b>Botdan to'liq foydalanish uchun kanalimizga a'zo bo'lishingiz shart!</b>"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url="https://t.me/aeroonex")],
        [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")]
    ])
    await message.reply(sub_text, reply_markup=keyboard, parse_mode="HTML")

def search_soundcloud_multi(query: str, limit=10):
    ydl_opts = {'quiet': True, 'noplaylist': True, 'skip_download': True, 'source_address': '0.0.0.0'}
    results = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    results.append({
                        'title': entry.get('title', 'Noma\'lum nom'),
                        'url': entry.get('url') or entry.get('webpage_url'),
                        'uploader': entry.get('uploader') or 'Noma\'lum Artist'
                    })
        except: pass
    return results

def download_by_url(url: str, output_path: str):
    ydl_opts = {
        'format': 'bestaudio/best', 
        'outtmpl': output_path + '.%(ext)s', 
        'quiet': True, 
        'noplaylist': True,
        'source_address': '0.0.0.0'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])

def escape_html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# --- START BUYRUG'I ---
@dp.message(Command('start'))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    admin_state.pop(user_id, None) 
    user_states.pop(user_id, None)
    
    full_name = message.from_user.full_name
    username = message.from_user.username
    args = message.text.split()
    
    if len(args) > 1 and args[1].startswith("anonim_"):
        target_id = int(args[1].split("_")[1])
        if target_id == user_id:
            await message.reply("😅 O'zingizga anonim xabar yozolmaysiz.")
            return
        user_states[user_id] = f"sending_anonim_{target_id}"
        await message.reply("🤫 <b>Ushbu foydalanuvchiga yubormoqchi bo'lgan anonim xabaringizni yozing:</b>\nIsmingiz sir saqlanadi.", parse_mode="HTML")
        return

    inviter_id = None
    if len(args) > 1 and args[1].isdigit():
        inviter_id = int(args[1])

    is_new = save_user(user_id, full_name, username, inviter_id)
    
    if is_new and not inviter_id and user_id != ADMIN_ID:
         asyncio.create_task(notify_user(ADMIN_ID, f"👤 <b>Yangi foydalanuvchi!</b>\nNomi: {escape_html(full_name)}\nID: <code>{user_id}</code>"))

    if user_id == ADMIN_ID:
        await message.reply("👋 Salom Admin!", reply_markup=get_admin_keyboard(), parse_mode="HTML")
        return

    welcome_text = (
        f"👋 <b>Salom, {escape_html(full_name)}! Botimizga xush kelibsiz!</b>\n\n"
        f"👉 <b>Musiqa topish uchun</b> shunchaki qo'shiq nomini yozib yuboring yoki ovozli xabar (voice)/video tashlang!\n"
        f"👉 <b>Instagram Reels/Post yuklash uchun</b> link tashlang!"
    )
    await message.reply(welcome_text, reply_markup=get_main_keyboard(), parse_mode="HTML")

# --- ASOSIY TEXT BOSHQARUVI ---
@dp.message(F.text)
async def handle_all_text(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if text == "❌ Bekor qilish" and user_states.get(user_id) == "waiting_card_details":
        user_states.pop(user_id, None)
        await message.reply("❌ Pul yechib olish so'rovi bekor qilindi.", reply_markup=get_main_keyboard())
        return

    if user_id == ADMIN_ID:
        if text == "📝 Foydalanuvchilarga xabar yuborish":
            admin_state[ADMIN_ID] = "waiting_for_post"
            cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)
            await message.reply("📨 Menga yuboriladigan xabarni (text, rasm yoki video) tashlang:", reply_markup=cancel_kb)
            return
        elif text == "❌ Bekor qilish" and admin_state.get(ADMIN_ID) == "waiting_for_post":
            admin_state.pop(ADMIN_ID, None)
            await message.reply("❌ Xabar yuborish bekor qilindi.", reply_markup=get_admin_keyboard())
            return
        elif text == "📊 Umumiy soni":
            users = load_users()
            await message.reply(f"📈 <b>Foydalanuvchilar soni:</b> {len(users)} ta", parse_mode="HTML")
            return
        elif text == "👥 Foydalanuvchilar ro'yxati":
            users = load_users()
            txt = "👥 <b>Oxirgi 15 ta foydalanuvchi:</b>\n\n"
            count = 0
            for uid, data in list(users.items())[-15:]:
                txt += f"👤 <b>Nomi:</b> {escape_html(data['name'])}\n🆔 ID: <code>{uid}</code>\n\n"
                count += 1
            if count == 0: txt = "Foydalanuvchilar mavjud emas."
            await message.reply(txt, parse_mode="HTML")
            return
        elif text == "🔙 Oddiy foydalanuvchi rejimiga qaytish":
            admin_state.pop(ADMIN_ID, None)
            await message.reply("Oddiy foydalanuvchi rejimiga qaytdingiz.", reply_markup=get_main_keyboard())
            return
        elif admin_state.get(ADMIN_ID) == "waiting_for_post":
            admin_state.pop(ADMIN_ID, None)
            users = load_users()
            await message.reply("🚀 Xabar barcha foydalanuvchilarga yuborilmoqda...", reply_markup=get_admin_keyboard())
            async def send_broadcast():
                success, fail = 0, 0
                for uid in users.keys():
                    try:
                        await message.copy_to(chat_id=int(uid))
                        success += 1
                        await asyncio.sleep(0.1)
                    except: fail += 1
                try: await bot.send_message(ADMIN_ID, f"🏁 <b>Yetkazildi:</b> {success}\n❌ <b>Bloklaganlar:</b> {fail}", parse_mode="HTML")
                except: pass
            asyncio.create_task(send_broadcast())
            return

    if user_states.get(user_id, "").startswith("sending_anonim_"):
        target_id = int(user_states[user_id].split("_")[2])
        user_states.pop(user_id, None)
        try:
            await bot.send_message(chat_id=target_id, text=f"🤫 <b>Sizga yangi anonim xabar keldi:</b>\n\n{escape_html(text)}", parse_mode="HTML")
            await message.reply("✅ Anonim xabaringiz yuborildi.")
        except:
            await message.reply("😔 Xabar yuborishda xatolik. Foydalanuvchi botni bloklagan bo'lishi mumkin.")
        return

    if user_states.get(user_id) == "waiting_card_details":
        user_states.pop(user_id, None)
        users = load_users()
        str_id = str(user_id)
        user_balance = users[str_id].get('balance', 0)
        
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"pay_yes_{user_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"pay_no_{user_id}")
            ]
        ])
        
        admin_text = (
            f"💸 <b>Pul yechishga so'rov!</b>\n\n"
            f"👤 Foydalanuvchi: {escape_html(message.from_user.full_name)}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💰 Yechiladigan summa: <b>{user_balance} so'm</b>\n"
            f"💳 Karta/Hisob: <code>{escape_html(text)}</code>\n\n"
            f"Tanlang:"
        )
        await bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=admin_kb, parse_mode="HTML")
        await message.reply("✅ <b>So'rovingiz adminga yuborildi!</b>\nAdmin tasdiqlaganidan so'ng mablag'ingiz yechiladi va o'tkaziladi.", reply_markup=get_main_keyboard(), parse_mode="HTML")
        return

    if text == "🎵 Musiqa qidirish":
        await message.reply("🎹 <b>Musiqa qidirish uchun:</b>\nShunchaki qo'shiq nomini yozib yuboring.\n\n<i>Masalan: Konsta - Havo</i>", parse_mode="HTML")
        return
    elif "Anonim Xabar" in text:
        anonim_link = f"https://t.me/oson_mediabot?start=anonim_{user_id}"
        await message.reply(f"🤫 <b>Sizning anonim xabar qabul qilish havolangiz:</b>\n\n<code>{anonim_link}</code>\n\nUshbu linkni storiesingizga qo'ying.", parse_mode="HTML")
        return
    elif "Pul ishlash" in text:
        ref_link = f"https://t.me/oson_mediabot?start={user_id}"
        pul_text = (
            f"💰 <b>Pul ishlash tizimi!</b>\n\n"
            f"Havolani do'stlaringizga tarqating. Har bir yangi odam uchun <b>500 so'm</b> olasiz!\n\n"
            f"🔗 <b>Sizning referal havolangiz:</b>\n<code>{ref_link}</code>"
        )
        await message.reply(pul_text, parse_mode="HTML")
        return
    elif "Kabinet" in text:
        users = load_users()
        str_id = str(user_id)
        if str_id not in users: return
        user_data = users[str_id]
        text_kabinet = (
            f"👤 <b>Sizning shaxsiy kabinetingiz</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📊 Takliflar: <b>{user_data.get('refs', 0)} ta</b>\n"
            f"💰 Balans: <b>{user_data.get('balance', 0)} so'm</b>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💸 Pulni yechib olish", callback_data="payout")]])
        await message.reply(text_kabinet, reply_markup=kb, parse_mode="HTML")
        return
    elif "Sevimlilar" in text or text == "/my":
        users = load_users()
        str_id = str(user_id)
        if str_id not in users or 'favorites' not in users[str_id] or not users[str_id]['favorites']:
            await message.reply("😔 Sevimlilar ro'yxatingiz bo'sh. Qo'shiqlarni ❤️ tugmasi orqali saqlang.")
            return
        favs = users[str_id]['favorites']
        txt = "❤️ <b>Sizning sevimlilar ro'yxatingiz:</b>\n\n"
        
        btns = []
        current_row = []
        for i, music in enumerate(favs[:20]):
            txt += f"<b>{i+1}.</b> {escape_html(music['title'])} — {escape_html(music['uploader'])}\n"
            current_row.append(InlineKeyboardButton(text=f"{i+1}", callback_data=f"myfav_{i}"))
            if len(current_row) == 4:
                btns.append(current_row)
                current_row = []
        if current_row: btns.append(current_row)
        txt += "\n📥 Qaysi birini yuklashni tanlaysiz?"
        await message.reply(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="HTML")
        return

    if re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/[\w-]+)', text):
        if not await check_subscription(user_id):
            await send_sub_alert(message)
            return
        status_msg = await message.reply("⌛️") 
        await handle_instagram_video(message, status_msg)
        return

    if not await check_subscription(user_id):
        await send_sub_alert(message)
        return
    status_msg = await message.reply(f"🔍 <b>'{escape_html(text)}' qidirilyapti...</b>", parse_mode="HTML")
    await process_text_search_with_custom_ui(message, text, status_msg, user_id)

# --- PUL YECHIB OLISH INLINE BOSHQARUVI ---
@dp.callback_query(F.data == "payout")
async def handle_payout_request(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    users = load_users()
    str_id = str(user_id)
    
    if str_id not in users: return
    user_balance = users[str_id].get('balance', 0)
    
    if user_balance < 1000:
        await callback_query.answer(f"😔 Minimal pul yechish summasi 1,000 so'm. Sizning balansingiz: {user_balance} so'm", show_alert=True)
        return
        
    user_states[user_id] = "waiting_card_details"
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)
    
    await bot.send_message(
        chat_id=user_id, 
        text="💳 <b>Pul o'tkaziladigan karta raqami yoki click raqamingizni yuboring:</b>\nMasalan: <code>8600 1234 5678 9012</code>",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )
    await callback_query.answer()

# --- ADMINNING TASDIQLASH YOKI RAD ETISHI ---
@dp.callback_query(F.data.startswith("pay_"))
async def handle_admin_payment_decision(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Siz admin emassiz!")
        return
        
    action = callback_query.data.split("_")[1] 
    target_user_id = callback_query.data.split("_")[2]
    
    users = load_users()
    
    if target_user_id not in users:
        await callback_query.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return
        
    user_balance = users[target_user_id].get('balance', 0)
    
    if action == "yes":
        users[target_user_id]['balance'] = 0
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
            
        await bot.send_message(
            chat_id=int(target_user_id), 
            text=f"🎉 <b>Sizning pul yechish so'rovingiz tasdiqlandi!</b>\n<b>{user_balance} so'm</b> o'tkazildi.", 
            parse_mode="HTML"
        )
        
        await callback_query.message.edit_text(f"✅ Ushbu foydalanuvchiga <b>{user_balance} so'm</b> yechildi va tasdiqlandi.", parse_mode="HTML")
        await callback_query.answer("To'lov tasdiqlandi.")
        
    elif action == "no":
        await bot.send_message(
            chat_id=int(target_user_id), 
            text="❌ <b>Sizning pul yechish so'rovingiz admin tomonidan rad etildi!</b>\nHisobingizdagi pul saqlanib qoldi.", 
            parse_mode="HTML"
        )
        
        await callback_query.message.edit_text(f"❌ So'rov rad etildi. Foydalanuvchining puli hisobida qoldi.", parse_mode="HTML")
        await callback_query.answer("To'lov rad etildi.")

# --- INSTAGRAM YUKLASH (YANGILANGAN) ---
async def handle_instagram_video(message: types.Message, status_msg: types.Message):
    chat_id = message.from_user.id
    url = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/[\w-]+)', message.text).group(1)
    
    await status_msg.edit_text("⏳ <b>Video yuklab olinyapti...</b>", parse_mode="HTML")
    
    local_file = os.path.join(BASE_DIR, f"insta_{message.message_id}.mp4")
    
    # MUHIM O'ZGARISH: Ovoz va videoni to'liq bitta mp4 qilib olish uchun sozlama yangilandi
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': local_file,
        'quiet': True,
        'noplaylist': True,
        'merge_output_format': 'mp4',
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None
    }
    
    try:
        def extract_and_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, extract_and_download)
        
        if os.path.exists(local_file):
            await status_msg.delete()
            caption = get_marketing_caption("Instagram", "Post")
            
            msg = await bot.send_video(chat_id=chat_id, video=FSInputFile(local_file), caption=caption, parse_mode="HTML")
            
            video_storage_cache[local_file] = time.time()
            
            cache_key = f"vid_{message.message_id}"
            save_file_to_cache(cache_key, msg.video.file_id, "video", {"title": "Instagram Video", "uploader": "Oson Media Bot"})
            
            video_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎵 Qo'shiqni yuklab olish", callback_data=f"shz_v_{cache_key}")],
                [InlineKeyboardButton(text="🔗 Do'stlarga ulashish", switch_inline_query=cache_key)]
            ])
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg.message_id, reply_markup=video_kb)
        else:
            raise Exception("Video fayli topilmadi.")
            
    except Exception as e:
        print(f"Instagram Yuklash Xatosi: {e}")
        await bot.send_message(
            chat_id=chat_id, 
            text="😔 <b>Videoni yuklab bo'lmadi.</b>\nKuki fayli eskirgan yoki havola xato.", 
            parse_mode="HTML"
        )
        try: await status_msg.delete()
        except: pass
        if os.path.exists(local_file):
            try: os.remove(local_file)
            except: pass

# --- FOYDALANUVCHI TO'G'RIDAN TO'G'RI VIDEO TASHALASA ---
@dp.message(F.video)
async def handle_user_sent_video(message: types.Message):
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        await send_sub_alert(message)
        return
        
    status_msg = await message.reply("🌀 <b>Videodan musiqa tahlil qilinyapti...</b>", parse_mode="HTML")
    
    video_file = await bot.get_file(message.video.file_id)
    local_video = os.path.join(BASE_DIR, f"direct_vid_{message.message_id}.mp4")
    local_audio = os.path.join(BASE_DIR, f"direct_aud_{message.message_id}.mp3")
    
    try:
        await bot.download_file(video_file.file_path, local_video)
        subprocess.run(
            f"ffmpeg -i {local_video} -vn -ar 44100 -ac 2 -b:a 128k {local_audio} -y", 
            shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        loop = asyncio.get_event_loop()
        result = json.loads(await loop.run_in_executor(None, recognizer.recognize_by_file, local_audio, 0))
            
        if result['status']['code'] == 0 and 'metadata' in result:
            music = result['metadata']['music'][0]
            query = f"{music['artists'][0]['name']} - {music['title']}"
            await status_msg.edit_text(f"🔍 <b>Musiqa topildi:</b> '{escape_html(query)}'\n\nQidirib yuklab olishingiz mumkin:", parse_mode="HTML")
            await process_text_search_with_custom_ui(message, query, status_msg, user_id, limit=10)
        else:
            await status_msg.edit_text("😔 Afsuski, ushbu videodan musiqa aniqlay olmadim.", parse_mode="HTML")
            
        if os.path.exists(local_video): os.remove(local_video)
        if os.path.exists(local_audio): os.remove(local_audio)
        
    except Exception as e:
        await status_msg.edit_text("😔 Tahlil jarayonida xatolik yuz berdi.", parse_mode="HTML")
        if os.path.exists(local_video): os.remove(local_video)
        if os.path.exists(local_audio): os.remove(local_audio)

# --- SHAZAM MANTIQI (INSTAGRAM TUGMASI UCHUN) ---
@dp.callback_query(F.data.startswith("shz_v_"))
async def process_video_shazam(callback_query: types.CallbackQuery):
    cache_key = callback_query.data.split("shz_v_")[1]
    message_id = cache_key.split("_")[1]
    
    video_path = None
    for file in os.listdir(BASE_DIR):
        if file.startswith(f"insta_{message_id}"):
            video_path = os.path.join(BASE_DIR, file)
            break
            
    if not video_path or not os.path.exists(video_path):
        await callback_query.answer("😔 Kechirasiz, video keshdan o'chib ketgan. Havolani qayta yuboring.", show_alert=True)
        return
        
    await callback_query.answer("🌀 Qo'shiq tahlil qilinyapti...")
    status_msg = await callback_query.message.answer("🌀 <b>Videodan musiqa tahlil qilinyapti...</b>", parse_mode="HTML")
    
    local_audio = os.path.join(BASE_DIR, f"temp_aud_{callback_query.id}.mp3")
    
    try:
        subprocess.run(
            f"ffmpeg -i {video_path} -vn -ar 44100 -ac 2 -b:a 128k {local_audio} -y", 
            shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        loop = asyncio.get_event_loop()
        result = json.loads(await loop.run_in_executor(None, recognizer.recognize_by_file, local_audio, 0))
            
        if result['status']['code'] == 0 and 'metadata' in result:
            music = result['metadata']['music'][0]
            query = f"{music['artists'][0]['name']} - {music['title']}"
            await status_msg.edit_text(f"🔍 <b>Musiqa topildi:</b> '{escape_html(query)}'\n\nQuyidagilardan tanlang:", parse_mode="HTML")
            await process_text_search_with_custom_ui(callback_query.message, query, status_msg, callback_query.from_user.id, limit=10)
        else:
            await status_msg.edit_text("😔 Afsuski, ushbu videodan musiqa aniqlay olmadim.", parse_mode="HTML")
            
        if os.path.exists(local_audio): os.remove(local_audio)
        
    except Exception as e:
        await status_msg.edit_text("😔 Tahlil jarayonida xatolik yuz berdi.", parse_mode="HTML")
        if os.path.exists(local_audio): os.remove(local_audio)

# --- MATNLI QIDIRUV VA NATIJALAR ---
async def process_text_search_with_custom_ui(message, query, status_msg, target_chat_id, limit=10):
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, search_soundcloud_multi, query, limit)
    if not results: return await status_msg.edit_text("😔 Topilmadi.")
    search_cache[target_chat_id] = results
    
    txt = f"🎧 <b>Siz uchun topilgan musiqalar:</b>\n\n"
    for i, res in enumerate(results): 
        txt += f"<b>{i+1}.</b> {escape_html(res['title'])} — {escape_html(res['uploader'])}\n"
        
    btns = []
    current_row = []
    for i in range(len(results)):
        current_row.append(InlineKeyboardButton(text=f"{i+1}", callback_data=f"dl_{i}"))
        if len(current_row) == 4: 
            btns.append(current_row)
            current_row = []
    if current_row: btns.append(current_row)
    await status_msg.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="HTML")

# --- YUKLAB OLISH ---
@dp.callback_query(F.data.startswith("dl_"))
async def handle_download_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    index = int(callback_query.data.split("_")[1])
    results = search_cache.get(user_id)
    if not results or index >= len(results): return
    selected = results[index]
    
    status_msg = await callback_query.message.answer(f"⏳ <b>Yuklanyapti...</b>", parse_mode="HTML")
    path = os.path.join(BASE_DIR, f"music_{callback_query.id}")
    
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, download_by_url, selected['url'], path)
        downloaded_file = None
        for file in os.listdir(BASE_DIR):
            if file.startswith(f"music_{callback_query.id}"):
                downloaded_file = os.path.join(BASE_DIR, file)
                break
                
        if downloaded_file:
            audio_msg = await bot.send_audio(
                chat_id=user_id, 
                audio=FSInputFile(downloaded_file), 
                title=selected['title'], 
                performer=selected['uploader'], 
                caption=get_marketing_caption(selected['title'], selected['uploader']),
                parse_mode="HTML"
            )
            
            cache_key = f"aud_{audio_msg.audio.file_id[:15]}"
            save_file_to_cache(cache_key, audio_msg.audio.file_id, "audio", {"title": selected['title'], "uploader": selected['uploader']})
            
            selected_key = f"sel_{user_id}_{index}"
            save_file_to_cache(selected_key, "none", "selected_info", selected)
            
            keyboard = get_share_keyboard(selected['title'], index=index, share_id=cache_key)
            await bot.edit_message_reply_markup(chat_id=user_id, message_id=audio_msg.message_id, reply_markup=keyboard)
            
            await status_msg.delete()
            os.remove(downloaded_file)
        else: raise Exception("Xato")
    except: 
        await status_msg.edit_text("😔 Yuklab bo'lmadi.")
        if os.path.exists(path): os.remove(path)

# --- SEVIMLILARGA QO'SHISH ---
@dp.callback_query(F.data.startswith("like_"))
async def process_favorites_like(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    index = int(callback_query.data.split("_")[1])
    
    selected_key = f"sel_{user_id}_{index}"
    cache = load_file_cache()
    
    if selected_key in cache:
        music_data = cache[selected_key]['data']
        res = update_user_favorites(user_id, music_data)
        if res:
            await callback_query.answer("❤️ Sevimlilar ro'yxatiga qo'shildi!", show_alert=True)
        else:
            await callback_query.answer("Bu musiqa allaqachon sevimlilaringizda bor.", show_alert=True)
    else:
        await callback_query.answer("Xatolik! Iltimos, musiqani qayta qidirib ko'ring.", show_alert=True)

@dp.callback_query(F.data.startswith("myfav_"))
async def handle_myfav_click(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    index = int(callback_query.data.split("_")[1])
    
    users = load_users()
    str_id = str(user_id)
    if str_id not in users or 'favorites' not in users[str_id]: return
    
    favs = users[str_id]['favorites']
    if index >= len(favs): return
    selected = favs[index]
    
    status_msg = await callback_query.message.answer(f"⏳ <b>Sevimlilardan yuklanyapti...</b>", parse_mode="HTML")
    path = os.path.join(BASE_DIR, f"music_fav_{callback_query.id}")
    
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, download_by_url, selected['url'], path)
        downloaded_file = None
        for file in os.listdir(BASE_DIR):
            if file.startswith(f"music_fav_{callback_query.id}"):
                downloaded_file = os.path.join(BASE_DIR, file)
                break
                
        if downloaded_file:
            await bot.send_audio(
                chat_id=user_id, 
                audio=FSInputFile(downloaded_file), 
                title=selected['title'], 
                performer=selected['uploader'], 
                caption=get_marketing_caption(selected['title'], selected['uploader']),
                parse_mode="HTML"
            )
            await status_msg.delete()
            os.remove(downloaded_file)
    except:
        await status_msg.edit_text("😔 Yuklab bo'lmadi.")
        if os.path.exists(path): os.remove(path)

# --- INLINE QUERY ---
@dp.inline_query()
async def inline_share_handler(inline_query: InlineQuery):
    query = inline_query.query
    results = []
    cache = load_file_cache()
    
    if query in cache:
        item = cache[query]
        file_id = item['file_id']
        file_type = item['type']
        
        if file_type == "audio":
            results.append(
                InlineQueryResultAudio(
                    id=query,
                    audio_file_id=file_id,
                    title=item['data'].get('title', 'Musiqa'),
                    caption=get_clean_caption(item['data'].get('title', 'Musiqa'), item['data'].get('uploader', 'Artist')),
                    parse_mode="HTML"
                )
            )
        elif file_type == "video":
            results.append(
                InlineQueryResultCachedVideo(
                    id=query,
                    video_file_id=file_id,
                    title="Instagram Video",
                    description="Oson Media orqali yuklangan video",
                    caption=get_clean_caption("Instagram", "Post"),
                    parse_mode="HTML"
                )
            )
            
    await inline_query.answer(results, cache_time=1)

@app.get('/')
async def home(): return "Bot faol!"
