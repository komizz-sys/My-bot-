import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ============================================================
# SOZLAMALAR
# ============================================================

BOT_TOKEN = "8858887305:AAHPvvD_-L682T48XhGvpjgUQKAaFSpV-4c"
API_ID = 37460790
API_HASH = "4473d7e19ab42ced7ff0ff02e3817b8f"
ADMIN_ID = 7942588812

TARGET_BOTS = [
    "RenewPrebotmium10_bot",
    "RenewPre3bot",
    "IPremium8_Renewbot",
    "GardanBegirbot",
    "RePreAmooBot",
]

DB_NAME = "bot.db"
latest_bot_messages = {}

# Userbot uchun so'rovlar navbati (Queue)
request_queue = asyncio.Queue()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# Railway'dagi SESSION environment variable'ni xavfsiz o'qish
session_string = os.environ.get("SESSION", "").strip()
if not session_string:
    logging.warning("DIQQAT: Railway'da SESSION topilmadi yoki bo'sh!")

userbot = TelegramClient(StringSession(session_string), API_ID, API_HASH)

# ============================================================
# TELETHON: TARGET BOTLARni KUZATISH
# ============================================================

@userbot.on(events.NewMessage(incoming=True))
async def capture_target_bot_messages(event):
    sender = await event.get_sender()
    if sender and sender.username:
        username = sender.username
        if username in TARGET_BOTS:
            text = event.message.text
            latest_bot_messages[username] = text
            logging.info(f"@{username} dan yangi xabar keldi: {text}")
            
            try:
                active_num = db.execute("SELECT number FROM numbers WHERE status = 'busy' ORDER BY id DESC LIMIT 1").fetchone()
                if active_num:
                    db.execute("UPDATE numbers SET code = ? WHERE number = ? AND status = 'busy'", (text, active_num["number"]))
                    db.commit()
            except Exception as e:
                logging.error(f"Kodlarni bazaga yozish xatoligi: {e}")

# ============================================================
# DATABASE SETUP
# ============================================================

db = sqlite3.connect(DB_NAME, check_same_thread=False)
db.row_factory = sqlite3.Row

def init_db():
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            is_approved INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            user_id INTEGER PRIMARY KEY,
            total INTEGER DEFAULT 0,
            canceled INTEGER DEFAULT 0,
            frozen INTEGER DEFAULT 0,
            codes INTEGER DEFAULT 0,
            premium INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            number TEXT UNIQUE NOT NULL,
            code TEXT,
            password TEXT,
            status TEXT DEFAULT 'active',
            expires_at TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("INSERT OR IGNORE INTO settings(key, value) VALUES ('target_bot', 'RenewPrebotmium10_bot')")
    cursor.execute("INSERT OR IGNORE INTO settings(key, value) VALUES ('bot_status', 'active')")
    
    db.commit()

init_db()

# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_setting(key, default=None):
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(key, value):
    db.execute("""
        INSERT INTO settings(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    db.commit()

def ensure_user(user: types.User):
    existing = db.execute("SELECT is_approved FROM users WHERE user_id = ?", (user.id,)).fetchone()
    is_new = not existing
    approved_status = 1 if user.id == ADMIN_ID else 0

    db.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, is_approved, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user.id, user.username or "", user.first_name or "", approved_status, now()))

    db.execute("INSERT OR IGNORE INTO stats(user_id) VALUES (?)", (user.id,))
    db.commit()

    if is_new and user.id != ADMIN_ID:
        try:
            name = user.first_name or "Noma'lum"
            uname = f"@{user.username}" if user.username else "Kiritmagan"
            admin_text = f"🚨 **Yangi foydalanuvchi!**\n\n👤 Ismi: {name}\n🔗 Username: {uname}\n🆔 ID: `{user.id}`"
            
            inline_kb = types.InlineKeyboardMarkup(row_width=2)
            inline_kb.add(
                types.InlineKeyboardButton("✅ Ruxsat berish", callback_data=f"approve_usr_{user.id}"),
                types.InlineKeyboardButton("❌ Rad etish", callback_data=f"block_usr_{user.id}")
            )
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(bot.send_message(ADMIN_ID, admin_text, reply_markup=inline_kb, parse_mode="Markdown"))
        except Exception as e:
            logging.error(f"Admin xabari xatoligi: {e}")

def is_allowed(user_id):
    if user_id == ADMIN_ID:
        return True
    row = db.execute("SELECT is_approved, is_blocked FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return False
    if row["is_blocked"]:
        return False
    return bool(row["is_approved"])

def change_stat(user_id, field, amount=1):
    db.execute(f"UPDATE stats SET {field} = {field} + ? WHERE user_id = ?", (amount, user_id))
    db.commit()

# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("📞 Raqam olish")
    keyboard.row("📊 Statistikam", "🎧 Yordamchi")
    return keyboard

def admin_keyboard():
    bot_status = get_setting("bot_status", "active")
    status_text = "🟢 Bot Ishlamoqda (To'xtatish)" if bot_status == "active" else "🔴 Bot Dam Olishda (Yoqish)"
    
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("🎯 Target bot tanlash", callback_data="admin_target"),
        types.InlineKeyboardButton(status_text, callback_data="toggle_bot_status"),
        types.InlineKeyboardButton("🔄 Statistikani 0 ga tushirish", callback_data="admin_reset_stats"),
        types.InlineKeyboardButton("👥 Foydalanuvchilar ro'yxati / Ban", callback_data="admin_users"),
    )
    return keyboard

# ============================================================
# HANDLERS: START & ADMIN PANEL
# ============================================================

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    ensure_user(message.from_user)
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Siz botdan foydalanish huquqiga ega emassiz yoki bloklangansiz.", parse_mode="Markdown")
        return

    await message.answer(
        "👋 **Xush kelibsiz!**\n\n"
        "Ushbu bot orqali har bir raqamga Telegram Premium olib daromad qilishingiz mumkin.\n"
        "Raqam olish uchun pastdagi tugmani bosing.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

@dp.message_handler(commands=["admin"])
async def admin_handler(message: types.Message):
    ensure_user(message.from_user)
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer("👑 **ADMIN PANEL**", reply_markup=admin_keyboard(), parse_mode="Markdown")

@dp.message_handler(commands=["check"])
async def admin_check_user_command(message: types.Message):
    ensure_user(message.from_user)
    
    args = message.text.split()
    
    if message.from_user.id == ADMIN_ID and len(args) > 1:
        try:
            target_id = int(args[1])
        except ValueError:
            await message.answer("❌ Noto'g'ri ID kiritildi. Masalan: `/check 12345678`", parse_mode="Markdown")
            return
    else:
        if not is_allowed(message.from_user.id):
            return
        target_id = message.from_user.id

    user = db.execute("SELECT first_name, username, is_approved, is_blocked FROM users WHERE user_id = ?", (target_id,)).fetchone()
    stats = db.execute("SELECT * FROM stats WHERE user_id = ?", (target_id,)).fetchone()

    if not user:
        await message.answer("❌ Bunday ID raqamli foydalanuvchi bazadan topilmadi.", parse_mode="Markdown")
        return

    name = user["first_name"] if user["first_name"] else "Noma'lum"
    uname = f"@{user['username']}" if user["username"] else "Kiritmagan"
    approved = "✅ Tasdiqlangan" if user["is_approved"] else "❌ Tasdiqlanmagan"
    blocked = "🔴 Bloklangan" if user["is_blocked"] else "🟢 Faol"

    text = (
        f"👤 **Foydalanuvchi ma'lumotlari:**\n\n"
        f"🆔 ID: `{target_id}`\n"
        f"📛 Ismi: {name}\n"
        f"🔗 Username: {uname}\n"
        f"📌 Holati: {approved} | {blocked}\n\n"
        f"📊 **Statistikasi:**\n"
        f"📞 Jami raqamlar: {stats['total'] if stats else 0}\n"
        f"❌ Bekor qilingan: {stats['canceled'] if stats else 0}\n"
        f"🧊 Muzlatilgan: {stats['frozen'] if stats else 0}\n"
        f"📨 Kodlar: {stats['codes'] if stats else 0}\n"
        f"⭐ Premium: {stats['premium'] if stats else 0}\n"
        f"💰 Balans: {stats['balance'] if stats else 0} so'm"
    )
    
    await message.answer(text, parse_mode="Markdown")

@dp.callback_query_handler(text="toggle_bot_status")
async def toggle_bot_status(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    current = get_setting("bot_status", "active")
    new_status = "rest" if current == "active" else "active"
    set_setting("bot_status", new_status)
    
    status_label = "dam olish rejimiga o'tkazildi 🔴" if new_status == "rest" else "faollashtirildi 🟢"
    await call.answer(f"Bot {status_label}", show_alert=True)
    await call.message.edit_reply_markup(reply_markup=admin_keyboard())

@dp.callback_query_handler(text="admin_reset_stats")
async def admin_reset_stats_callback(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    db.execute("UPDATE stats SET total = 0, canceled = 0, frozen = 0, codes = 0, premium = 0")
    db.commit()
    await call.answer("✅ Barcha foydalanuvchilar statistikasi 0 ga tushirildi!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith("approve_usr_") or c.data.startswith("block_usr_"))
async def process_user_approval(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    parts = call.data.split("_")
    action, target_id = parts[0], int(parts[2])

    val = 1 if action == "approve" else 0
    db.execute("UPDATE users SET is_approved = ? WHERE user_id = ?", (val, target_id))
    db.commit()

    await call.message.edit_text(call.message.text + f"\n\n**Holat o'zgartirildi:** {action.upper()}", parse_mode="Markdown")
    if action == "approve":
        try:
            await bot.send_message(target_id, "🎉 So'rovingiz tasdiqlandi! /start ni bosing.", parse_mode="Markdown")
        except:
            pass

@dp.callback_query_handler(text="admin_target")
async def admin_target(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    current = get_setting("target_bot", TARGET_BOTS[0])
    for target in TARGET_BOTS:
        prefix = "✅ " if target == current else ""
        keyboard.add(types.InlineKeyboardButton(f"{prefix}@{target}", callback_data=f"set_target_{target}"))
    keyboard.add(types.InlineKeyboardButton("↩️ Orqaga", callback_data="admin_back"))
    await call.message.edit_text(f"🎯 Hozirgi target: `@{current}`", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith("set_target_"))
async def target_selected(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    target = call.data.split("_", 2)[2]
    set_setting("target_bot", target)
    await call.answer(f"@{target} tanlandi!", show_alert=True)
    await admin_target(call)

@dp.callback_query_handler(text="admin_users")
async def admin_users(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    rows = db.execute("""
        SELECT u.user_id, u.first_name, u.is_blocked, s.total 
        FROM users u LEFT JOIN stats s ON u.user_id = s.user_id
    """).fetchall()
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for r in rows:
        if r['user_id'] == ADMIN_ID:
            continue
        status_icon = "🔴 Ban" if r['is_blocked'] else "🟢 Faol"
        name = r['first_name'] or "Noma'lum"
        keyboard.add(
            types.InlineKeyboardButton(f"{name} ({status_icon})", callback_data=f"user_info_{r['user_id']}"),
        )
    keyboard.add(types.InlineKeyboardButton("↩️ Orqaga", callback_data="admin_back"))
    await call.message.edit_text("👥 **Foydalanuvchilar ro'yxati (Boshqarish uchun bosing):**", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith("user_info_"))
async def user_info_callback(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    target_id = int(call.data.split("_")[2])
    user = db.execute("SELECT * FROM users WHERE user_id = ?", (target_id,)).fetchone()
    
    if not user:
        await call.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return

    is_blocked = bool(user["is_blocked"])
    block_btn_text = "🟢 Unban qilish" if is_blocked else "🔴 Ban qilish"
    block_callback = f"unban_usr_{target_id}" if is_blocked else f"ban_usr_{target_id}"

    status_str = "Bloklangan ❌" if is_blocked else "Faol ✅"
    text = (
        f"👤 **Foydalanuvchi:** `{target_id}`\n"
        f"📛 Ismi: {user['first_name']}\n"
        f"🔗 Username: @{user['username']}\n"
        f"📌 Holati: {status_str}"
    )

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(block_btn_text, callback_data=block_callback),
        types.InlineKeyboardButton("↩️ Orqaga", callback_data="admin_users")
    )
    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith("ban_usr_") or c.data.startswith("unban_usr_"))
async def process_ban_unban(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    parts = call.data.split("_")
    action, target_id = parts[0], int(parts[2])

    val = 1 if action == "ban" else 0
    db.execute("UPDATE users SET is_blocked = ? WHERE user_id = ?", (val, target_id))
    db.commit()

    action_text = "bloklandi (ban qilindi)" if action == "ban" else "blokdan chiqarildi (unban qilindi)"
    await call.answer(f"Foydalanuvchi {action_text}!", show_alert=True)
    
    call.data = f"user_info_{target_id}"
    await user_info_callback(call)

@dp.callback_query_handler(text="admin_back")
async def admin_back(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.edit_text("👑 **ADMIN PANEL**", reply_markup=admin_keyboard(), parse_mode="Markdown")

# ============================================================
# STATS & HELP
# ============================================================

@dp.message_handler(lambda m: m.text in ["📊 Statistikam", "/stats"])
async def stats_handler(message: types.Message):
    ensure_user(message.from_user)
    if not is_allowed(message.from_user.id):
        return
    stats = db.execute("SELECT * FROM stats WHERE user_id = ?", (message.from_user.id,)).fetchone()
    text = (
        f"📊 **Sizning statistikangiz:**\n\n"
        f"📞 Jami raqamlar: {stats['total']}\n"
        f"❌ Bekor qilingan: {stats['canceled']}\n"
        f"🧊 Muzlatilgan: {stats['frozen']}\n"
        f"📨 Kodlar: {stats['codes']}\n"
        f"⭐ Premium: {stats['premium']}\n"
        f"💰 Balans: {stats['balance']} so'm"
    )
    await message.answer(text, reply_markup=main_keyboard(), parse_mode="Markdown")

@dp.message_handler(lambda m: m.text in ["🎧 Yordamchi", "/help"])
async def help_handler(message: types.Message):
    await message.answer("💬 Murojaat uchun admin: @vip_uzpek", reply_markup=main_keyboard())

# ============================================================
# NUMBER WORKER
# ============================================================

async def queue_worker():
    while True:
        target, message_obj = await request_queue.get()
        try:
            await userbot.send_message(target, "/getNumber")
            await asyncio.sleep(0.8)
        except Exception as e:
            logging.error(f"Queue worker xatoligi: {e}")
        finally:
            request_queue.task_done()

# ============================================================
# NUMBER MANAGEMENT
# ============================================================

@dp.message_handler(commands=["getNumber"])
@dp.message_handler(lambda m: m.text == "📞 Raqam olish")
async def get_number_cmd(message: types.Message):
    ensure_user(message.from_user)
    user_id = message.from_user.id
    if not is_allowed(user_id):
        return

    if get_setting("bot_status", "active") == "rest":
        await message.answer("🔴 Bot hozirda dam olish rejimida, yangi raqamlar berilmaydi.", reply_markup=main_keyboard())
        return

    active_num = db.execute(
        "SELECT * FROM numbers WHERE user_id = ? AND status = 'busy'", (user_id,)
    ).fetchone()
    if active_num:
        await message.answer(
            f"⚠️ Sizda allaqachon faol raqam bor: `{active_num['number']}`\n"
            "Iltimos, oldin uni tugating (Cancel yoki Check premium bosing).",
            parse_mode="Markdown"
        )
        return

    target = get_setting("target_bot", TARGET_BOTS[0])
    msg = await message.answer("⏳ Raqam olinmoqda...", parse_mode="Markdown")

    try:
        await request_queue.put((target, message))
        await asyncio.sleep(3.2)

        phone_number = latest_bot_messages.get(target, "").strip()
        if not phone_number or phone_number.startswith("/"):
            await msg.edit_text("❌ Hozircha bo'sh raqamlar yo'q yoki xatolik yuz berdi.", parse_mode="Markdown")
            return

        used_before = db.execute("SELECT id FROM numbers WHERE number = ? AND status = 'used'", (phone_number,)).fetchone()
        if used_before:
            await msg.edit_text("❌ Bu raqam allaqachon ishlatilgan. Qayta urinib ko'ring.", parse_mode="Markdown")
            return

        expires_time = datetime.now() + timedelta(minutes=30)
        
        db.execute("""
            INSERT INTO numbers (user_id, number, status, expires_at, created_at)
            VALUES (?, ?, 'busy', ?, ?)
        """, (user_id, phone_number, expires_time.strftime("%Y-%m-%d %H:%M:%S"), now()))
        db.commit()

        change_stat(user_id, "total", 1)

        inline_kb = types.InlineKeyboardMarkup(row_width=2)
        inline_kb.add(
            types.InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_num_{phone_number}"),
            types.InlineKeyboardButton("🧊 Freeze", callback_data=f"freeze_num_{phone_number}")
        )
        inline_kb.add(
            types.InlineKeyboardButton("📥 Get Code", callback_data=f"get_code_{phone_number}")
        )

        text = (
            f"📞 **Sizning raqamingiz:**\n\n`{phone_number}`\n\n"
            f"⏰ **Vaqt:** 30 daqiqa berildi.\n"
            f"Iltimos, shu vaqt ichida kodni oling va Premium ulang!"
        )
        await msg.edit_text(text, reply_markup=inline_kb, parse_mode="Markdown")

        asyncio.create_task(reminder_task(user_id, phone_number))

    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {e}", parse_mode="Markdown")

async def reminder_task(user_id, phone_number):
    await asyncio.sleep(600)
    row = db.execute("SELECT status FROM numbers WHERE number = ? AND user_id = ?", (phone_number, user_id)).fetchone()
    if row and row["status"] == 'busy':
        try:
            await bot.send_message(
                user_id,
                f"⚠️ **Eslatma:** `{phone_number}` raqamingiz uchun vaqt o'tmoqda! Iltimos, tezroq Premium ulang va tugmani bosing.",
                parse_mode="Markdown"
            )
        except:
            pass

@dp.callback_query_handler(lambda c: c.data.startswith("get_code_"))
async def get_code_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    phone_number = call.data.split("_", 2)[2]
    change_stat(user_id, "codes", 1)

    num_row = db.execute(
        "SELECT * FROM numbers WHERE number = ? AND user_id = ?", 
        (phone_number, user_id)
    ).fetchone()
    
    if not num_row:
        await call.answer("❌ Raqam topilmadi!", show_alert=True)
        return

    code = num_row["code"] if "code" in num_row.keys() and num_row["code"] else "Kutilmoqda ⏳"
    password = num_row["password"] if "password" in num_row.keys() and num_row["password"] else "Yo'q"

    text = (
        f"📩 **Code received:**\n\n"
        f"📞 **Number:** `{phone_number}`\n"
        f"🔐 **Code:** `{code}`\n"
        f"🔑 **Pass:** `{password}`"
    )

    updated_keyboard = types.InlineKeyboardMarkup(row_width=2)
    updated_keyboard.add(
        types.InlineKeyboardButton("🔄 Get code again", callback_data=f"get_code_{phone_number}"),
        types.InlineKeyboardButton("⭐ Check premium", callback_data=f"check_prem_{phone_number}")
    )
    updated_keyboard.add(
        types.InlineKeyboardButton("🧊 Freeze", callback_data=f"freeze_num_{phone_number}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_num_{phone_number}")
    )

    try:
        await call.message.edit_text(text, reply_markup=updated_keyboard, parse_mode="Markdown")
    except Exception as e:
        pass
    
    await call.answer("Yangilandi!")

@dp.callback_query_handler(lambda c: c.data.startswith("check_prem_"))
async def check_premium_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    phone_number = call.data.split("_", 2)[2]

    num_row = db.execute("SELECT * FROM numbers WHERE number = ? AND user_id = ? AND status = 'busy'", (phone_number, user_id)).fetchone()
    if not num_row:
        await call.answer("❌ Bu raqam topilmadi yoki vaqti tugagan!", show_alert=True)
        return

    target = get_setting("target_bot", TARGET_BOTS[0])
    waiting_msg = await call.message.answer("🔍 Premium holati tekshirilmoqda, iltimos kuting...", parse_mode="Markdown")

    try:
        await userbot.send_message(target, f"/check {phone_number}")
        await asyncio.sleep(2.5)

        bot_response = latest_bot_messages.get(target, "")

        await waiting_msg.delete()

        if "activated and counted" in bot_response:
            db.execute("UPDATE numbers SET status = 'success' WHERE number = ? AND user_id = ?", (phone_number, user_id))
            db.execute("UPDATE users SET balance = balance + 38500, premium = premium + 1 WHERE user_id = ?", (user_id,))
            db.commit()
            change_stat(user_id, "success", 1)

            try:
                await call.message.edit_reply_markup(reply_markup=None)
            except:
                pass

            await call.message.answer(f"🎉 **Tabriklaymiz!** Raqam (`{phone_number}`) uchun Premium tasdiqlandi va balansga 38,500 so'm qo'shildi.", parse_mode="Markdown")
            await call.answer("Muvaffaqiyatli tasdiqlandi!", show_alert=True)

        elif "is not premium" in bot_response:
            await call.message.answer(
                f"⚠️ **Diqqat!** `{phone_number}` raqamiga hali Telegram Premium ulanmagan (`is not premium`).\n\n"
                f"Iltimos, oldin raqamga Premium ulang, keyin qaytadan **Check premium** tugmasini bosing!",
                parse_mode="Markdown"
            )
            await call.answer("Premium hali olinmagan!", show_alert=True)
        else:
            await call.message.answer(
                f"⏳ Target botdan kutilgan javob kelmadi yoki tekshiruv vaqti cho'zildi.\nJavob: `{bot_response}`\n\nQayta urinib ko'ring.",
                parse_mode="Markdown"
            )
            await call.answer("Javob topilmadi", show_alert=True)

    except Exception as e:
        await waiting_msg.delete()
        await call.message.answer(f"❌ Tekshirishda xatolik yuz berdi: {e}", parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith("cancel_num_"))
async def cancel_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    phone_number = call.data.split("_", 2)[2]

    db.execute("UPDATE numbers SET status = 'canceled' WHERE number = ? AND user_id = ?", (phone_number, user_id))
    db.commit()
    change_stat(user_id, "canceled", 1)

    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except:
        pass
    await call.message.edit_text(f"❌ `{phone_number}` raqami bekor qilindi va bepul ro'yxatga qaytarildi.", parse_mode="Markdown")
    await call.answer()

# ============================================================
# BACKGROUND TIMEOUT CHECKER
# ============================================================

async def background_timeout_checker():
    while True:
        await asyncio.sleep(60)
        try:
            current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            expired_nums = db.execute(
                "SELECT * FROM numbers WHERE status = 'busy' AND expires_at <= ?", (current_time_str,)
            ).fetchall()

            for item in expired_nums:
                db.execute("UPDATE numbers SET status = 'canceled' WHERE id = ?", (item["id"],))
                db.commit()
                change_stat(item["user_id"], "canceled", 1)
                try:
                    await bot.send_message(
                        item["user_id"],
                        f"⏰ `{item['number']}` raqami uchun 30 daqiqalik vaqt tugadi va u avtomatik bekor qilindi.",
                        parse_mode="Markdown"
                    )
                except:
                    pass
        except Exception as e:
            logging.error(f"Timeout checker xatoligi: {e}")

# ============================================================
# STARTUP & SHUTDOWN
# ============================================================

async def on_startup(dispatcher):
    print("Userbot ulanmoqda...")
    await userbot.start()
    asyncio.create_task(queue_worker())
    asyncio.create_task(background_timeout_checker())
    print("Bot va Userbot muvaffaqiyatli ishga tushdi!")

async def on_shutdown(dispatcher):
    try:
        await userbot.disconnect()
        db.commit()
        db.close()
    except:
        pass

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)