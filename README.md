# 🎵 Oson Media Bot

Oson Media Bot — Telegram orqali Instagram videolarini (Reels, Post, IGTV) yuklash va qidirilgan musiqalarni tezkor topish uchun yaratilgan mukammal Telegram bot. Bot orqali foydalanuvchilar nafaqat media yuklashlari, balki do'stlarini taklif qilib pul ishlashlari hamda anonim xabarlar qabul qilishlari mumkin.

---

## 🚀 Asosiy Imkoniyatlar

* **Instagram Downloader:** Instagram havolalarini yuborish orqali sifatli video va audiolarni yuklab olish.
* **Musiqa Qidiruvi va Shazam:** Nomini yozish orqali yoki to'g'ridan-to'g'ri video/audio tashlash orqali musiqalarni tahlil qilib topish (ACRCloud texnologiyasi).
* **Anonim Xabarlar:** Foydalanuvchilar o'zlarining shaxsiy havolalari orqali ismlari sir qolgan holda xabarlar olishi mumkin.
* **Referal Tizimi:** Har bir taklif qilingan foydalanuvchi uchun bot balansiga bonus mablag' qo'shiladi.
* **Pul Yechish Tizimi:** Foydalanuvchilar ishlagan pullarini karta raqamlarini kiritib, admin tasdiqlaganidan so'ng yechib olishlari mumkin.
* **Majburiy Obuna:** Kanalga a'zo bo'lmaguncha botdan to'liq foydalanishni cheklash tizimi.
* **Admin Panel:** Bot foydalanuvchilariga xabar yuborish, foydalanuvchilar sonini ko'rish va pul yechish so'rovlarini boshqarish.

---

## 🛠 Texnologiyalar

Bot quyidagi zamonaviy texnologiyalar va kutubxonalar asosida qurilgan:

* **Dasturlash tili:** Python 3.12
* **Telegram Framework:** Aiogram 3.x (Asinxron)
* **Web Framework:** FastAPI (Ulanish va bot faolligini saqlash uchun)
* **Yuklab oluvchi vosita:** `yt-dlp` (Instagram va boshqa platformalar uchun)
* **Audio Tahlil:** ACRCloud API (Shazam kabi ishlash uchun)
* **Fayllarni boshqarish:** FFmpeg (Video va audiolarni qayta ishlash uchun)

---

## 💻 O'rnatish va Ishga tushirish

Loyiha kodini serveringizga yoki mahalliy kompyuteringizga o'rnatish uchun quyidagi amallarni bajaring:

### 1. Loyihani yuklab olish:
```bash
git clone [https://github.com/aeroonex/oson-media-bot.git](https://github.com/aeroonex/oson-media-bot.git)
cd oson-media-bot
2. Virtual muhit yaratish va kerakli kutubxonalarni o'rnatish:
Bash
python3 -m venv venv
source venv/bin/activate
pip install aiogram fastapi aiohttp yt-dlp acrcloud uvicorn
3. Kodni sozlash:
main.py faylini ochib, quyidagi o'zgaruvchilarga o'z ma'lumotlaringizni kiriting:

TOKEN — Telegram Bot tokeningiz.

CHANNEL_ID — Majburiy obuna qilinadigan kanal manzili.

ADMIN_ID — Sizning Telegram ID raqamingiz.

ACR_CONFIG — ACRCloud platformasidan olingan kalitlar.

4. Botni ishga tushirish:
Bash
uvicorn main:app --host 0.0.0.0 --port 8000
