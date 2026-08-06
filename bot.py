import telebot
from telebot import types
import sqlite3
from datetime import datetime
import time

TOKEN = "8943795430:AAHqKa66HhnO67BV00vDVuO4hHp0qFtJPLc"
ADMIN_ID = 8879412585

CARD_NUMBER = "5022291508007356"
CARD_NAME = "بهزاد بافهم"

bot = telebot.TeleBot(TOKEN)

# ================= وضعیت خاموش/روشن =================
bot_active = True  # True = فعال، False = خاموش

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("vpnbot.db")
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        purchases INTEGER DEFAULT 0,
        join_date TEXT
    )
    """)
    
    cur.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cur.fetchall()]
    if 'join_date' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN join_date TEXT")
        cur.execute("UPDATE users SET join_date = ? WHERE join_date IS NULL", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plan TEXT,
        price INTEGER,
        status TEXT,
        order_date TEXT,
        sub_link TEXT
    )
    """)
    
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect("vpnbot.db")
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id=?", (user_id,))
    exists = cur.fetchone()
    if not exists:
        cur.execute("INSERT INTO users (id, username, join_date) VALUES (?, ?, ?)",
                    (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    conn.close()

def update_purchases(user_id):
    conn = sqlite3.connect("vpnbot.db")
    cur = conn.cursor()
    cur.execute("SELECT purchases FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    if row:
        purchases = row[0] + 1
        cur.execute("UPDATE users SET purchases=? WHERE id=?", (purchases, user_id))
    else:
        purchases = 1
        cur.execute("INSERT INTO users (id, purchases) VALUES (?, ?)", (user_id, purchases))
    conn.commit()
    conn.close()
    return purchases

def get_purchases(user_id):
    conn = sqlite3.connect("vpnbot.db")
    cur = conn.cursor()
    cur.execute("SELECT purchases FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

def save_order(user_id, plan, price):
    conn = sqlite3.connect("vpnbot.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO orders (user_id, plan, price, status, order_date) VALUES (?, ?, ?, ?, ?)",
                (user_id, plan, price, "pending", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id

def update_order_status(order_id, status, sub_link=None):
    conn = sqlite3.connect("vpnbot.db")
    cur = conn.cursor()
    if sub_link:
        cur.execute("UPDATE orders SET status=?, sub_link=? WHERE id=?", (status, sub_link, order_id))
    else:
        cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()

def get_user_orders(user_id):
    conn = sqlite3.connect("vpnbot.db")
    cur = conn.cursor()
    cur.execute("SELECT plan, price, status, order_date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_stats():
    conn = sqlite3.connect("vpnbot.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    cur.execute("SELECT SUM(purchases) FROM users")
    total_purchases = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM users WHERE purchases > 0 AND purchases % 5 = 0")
    total_gifted = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
    pending_count = cur.fetchone()[0]
    conn.close()
    return total_users, total_purchases, total_gifted, pending_count

def get_all_users():
    conn = sqlite3.connect("vpnbot.db")
    cur = conn.cursor()
    cur.execute("SELECT id, username, purchases, join_date FROM users ORDER BY purchases DESC")
    rows = cur.fetchall()
    conn.close()
    return rows

# ================= GLOBAL =================
user_plans = {}
waiting_for_receipt = set()
waiting_for_sub_link = False
temp_user_id = None
temp_order_id = None

plan_prices = {
    "plan_20": 150,
    "plan_30": 200,
    "plan_40": 250,
    "plan_50": 300
}

plan_names = {
    "plan_20": "📦 20 گیگ - 150 تومان - کاربر نامحدود -دوماهه ",
    "plan_30": "📦 30 گیگ - 200 تومان - کاربر نامحدود -دوماهه ",
    "plan_40": "📦 40 گیگ - 250 تومان - کاربر نامحدود -دوماهه ",
    "plan_50": "📦 50 گیگ - 300 تومان - کاربر نامحدود -دوماهه "
}

# ================= KEYBOARDS =================
def main_keyboard(user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🛒 خرید اشتراک", "📦 خریدهای من", "📞 پشتیبانی")
    if user_id == ADMIN_ID:
        markup.add("⚙️ پنل ادمین")
    return markup

def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 آمار", "👥 کاربران", "⏳ سفارشات", "📨 پیام", "📢 همگانی", "🔙 منو اصلی")
    # دکمه خاموش/روشن
    status_text = "🔴 خاموش کردن ربات" if bot_active else "🟢 روشن کردن ربات"
    markup.add(status_text)
    return markup

# ================= START =================
@bot.message_handler(commands=['start'])
def start_cmd(msg):
    add_user(msg.from_user.id, msg.from_user.username or "unknown")
    welcome_text = """
🎉 به ربات فروش VPN خوش آمدید 🎉

🔥 مزایا:
✅ سرورهای پرسرعت از لوکیشن های مختلف
✅ پشتیبانی سریع ۲۴ ساعته
✅ سرورهای پایدار با کیفیت بالا

📱 از دکمه‌های منو استفاده کنید 👇
"""
    bot.send_message(msg.chat.id, welcome_text, reply_markup=main_keyboard(msg.from_user.id))

# ================= چک کردن وضعیت ربات قبل از هر اقدام =================
def is_bot_active():
    return bot_active

# ================= USER BUTTONS =================
@bot.message_handler(func=lambda m: m.text == "🛒 خرید اشتراک")
def buy_handler(msg):
    if not bot_active and msg.from_user.id != ADMIN_ID:
        bot.send_message(msg.chat.id, "⚠️ با عرض پوزش، سرور در حال بروزرسانی میباشد. لطفا بعدا مراجعه کنید.")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, name in plan_names.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=key))
    bot.send_message(msg.chat.id, "📱 پلن مورد نظر را انتخاب کنید:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📦 خریدهای من")
def my_purchases_handler(msg):
    if not bot_active and msg.from_user.id != ADMIN_ID:
        bot.send_message(msg.chat.id, "⚠️ با عرض پوزش، سرور در حال بروزرسانی میباشد. لطفا بعدا مراجعه کنید.")
        return
    uid = msg.from_user.id
    purchases = get_purchases(uid)
    orders = get_user_orders(uid)
    remaining = 5 - (purchases % 5)
    if remaining == 5:
        remaining = 0
    
    text = f"""
📊 اطلاعات حساب شما

🛒 تعداد کل خرید: {purchases}

"""
    if orders:
        text += "\n📋 سفارشات اخیر:\n"
        for plan, price, status, date in orders:
            emoji = "✅" if status == "completed" else "⏳"
            text += f"{emoji} {plan}\n   💰 {price} تومان - {date[:10]}\n"
    else:
        text += "\n📭 هنوز خریدی انجام نداده‌اید."
    
    bot.send_message(uid, text)

@bot.message_handler(func=lambda m: m.text == "📞 پشتیبانی")
def support_handler(msg):
    if not bot_active and msg.from_user.id != ADMIN_ID:
        bot.send_message(msg.chat.id, "⚠️ با عرض پوزش، سرور در حال بروزرسانی میباشد. لطفا بعدا مراجعه کنید.")
        return
    text = """
📞 راه‌های ارتباط با پشتیبانی:

🆔 آیدی تلگرام: @Mig_Mig_Vpn2

⏰ ساعت پاسخگویی: ۹ صبح تا ۱۲ شب

❓ سوالات متداول:
• بعد از خرید، لینک ساب برایتان ارسال می‌شود
• در صورت بروز مشکل، با پشتیبانی تماس بگیرید
• کلیه سرورها با بالاترین کیفیت ارائه می‌شوند
"""
    bot.send_message(msg.chat.id, text)

# ================= ADMIN BUTTONS =================
@bot.message_handler(func=lambda m: m.text == "⚙️ پنل ادمین" and m.from_user.id == ADMIN_ID)
def admin_panel(msg):
    stats = get_stats()
    text = f"📊 آمار فروش\n\n👥 کاربران ثبت شده: {stats[0]}\n🛒 مجموع خریدها: {stats[1]}\n🎁 کاربران هدیه گرفته: {stats[2]}\n⏳ سفارشات در انتظار: {stats[3]}"
    bot.send_message(ADMIN_ID, text, reply_markup=admin_keyboard())

# ================= دکمه خاموش/روشن =================
@bot.message_handler(func=lambda m: m.text in ["🔴 خاموش کردن ربات", "🟢 روشن کردن ربات"] and m.from_user.id == ADMIN_ID)
def toggle_bot(msg):
    global bot_active
    if "خاموش" in msg.text:
        bot_active = False
        bot.send_message(ADMIN_ID, "🔴 ربات خاموش شد. کاربران پیام بروزرسانی دریافت می‌کنند.")
    else:
        bot_active = True
        bot.send_message(ADMIN_ID, "🟢 ربات روشن شد. همه چیز فعال است.")
    # بروزرسانی کیبورد ادمین
    admin_panel(msg)  # مجدداً پنل ادمین را با دکمه جدید نشان می‌دهد

@bot.message_handler(func=lambda m: m.text == "📊 آمار" and m.from_user.id == ADMIN_ID)
def admin_stats(msg):
    stats = get_stats()
    bot.send_message(ADMIN_ID, f"👥 {stats[0]} کاربر\n🛒 {stats[1]} خرید\n🎁 {stats[2]} هدیه\n⏳ {stats[3]} سفارش")

@bot.message_handler(func=lambda m: m.text == "👥 کاربران" and m.from_user.id == ADMIN_ID)
def admin_users(msg):
    users = get_all_users()
    if not users:
        bot.send_message(ADMIN_ID, "❌ هیچ کاربری وجود ندارد.")
        return
    
    bot.send_message(ADMIN_ID, f"📋 تعداد کل کاربران: {len(users)}")
    
    for idx, (uid, username, pur, date) in enumerate(users, 1):
        uname = f"@{username}" if username and username != "unknown" else "بدون نام"
        text = f"{idx}. 🆔 {uid}\n👤 {uname}\n🛒 {pur} خرید\n📅 {date}\n━━━━━━━━━"
        try:
            bot.send_message(ADMIN_ID, text)
            time.sleep(0.05)
        except:
            pass
    
    bot.send_message(ADMIN_ID, "✅ پایان لیست")

@bot.message_handler(func=lambda m: m.text == "⏳ سفارشات" and m.from_user.id == ADMIN_ID)
def admin_orders(msg):
    conn = sqlite3.connect("vpnbot.db")
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, plan, order_date FROM orders WHERE status='pending'")
    orders = cur.fetchall()
    conn.close()
    if not orders:
        bot.send_message(ADMIN_ID, "✅ هیچ سفارش در انتظاری نیست.")
        return
    text = "⏳ سفارشات در انتظار تایید:\n\n"
    for oid, uid, plan, date in orders:
        text += f"📦 #{oid} - کاربر {uid}\n📋 {plan}\n📅 {date}\n━━━━━━━━━\n"
    bot.send_message(ADMIN_ID, text)

@bot.message_handler(func=lambda m: m.text == "📨 پیام" and m.from_user.id == ADMIN_ID)
def admin_msg_prompt(msg):
    global waiting_for_sub_link
    waiting_for_sub_link = "ask_user_id"
    bot.send_message(ADMIN_ID, "📌 ID کاربر را وارد کنید:")

@bot.message_handler(func=lambda m: m.text == "📢 همگانی" and m.from_user.id == ADMIN_ID)
def admin_broadcast_prompt(msg):
    global waiting_for_sub_link
    waiting_for_sub_link = "broadcast"
    bot.send_message(ADMIN_ID, "📌 متن پیام همگانی را وارد کنید:")

@bot.message_handler(func=lambda m: m.text == "🔙 منو اصلی" and m.from_user.id == ADMIN_ID)
def admin_back(msg):
    bot.send_message(ADMIN_ID, "🔙 بازگشت به منوی اصلی", reply_markup=main_keyboard(ADMIN_ID))

# ================= CALLBACKS =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_"))
def plan_callback(call):
    if not bot_active and call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ سرور در حال بروزرسانی، لطفا بعدا تلاش کنید.")
        return
    uid = call.from_user.id
    plan_key = call.data
    plan_name = plan_names[plan_key]
    plan_price = plan_prices[plan_key]
    
    order_id = save_order(uid, plan_name, plan_price)
    user_plans[uid] = {"plan": plan_name, "price": plan_price, "order_id": order_id}
    
    text = f"""
💳 اطلاعات پرداخت

📦 پلن: {plan_name}
💰 مبلغ: {plan_price} تومان

🏦 شماره کارت:
<code>{CARD_NUMBER}</code>

👤 نام صاحب حساب:
{CARD_NAME}

✅ بعد از واریز، دکمه زیر را بزنید:
"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ پرداخت کردم", callback_data="paid"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "paid")
def paid_callback(call):
    if not bot_active and call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ سرور در حال بروزرسانی، لطفا بعدا تلاش کنید.")
        return
    uid = call.from_user.id
    if uid not in user_plans:
        bot.answer_callback_query(call.id, "❌ خطا! دوباره پلن رو انتخاب کن")
        return
    waiting_for_receipt.add(uid)
    bot.send_message(uid, "📸 لطفاً تصویر رسید پرداخت را ارسال کنید.\n(فقط تصویر)")
    bot.answer_callback_query(call.id, "منتظر رسید ✅")

@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
def approve_callback(call):
    global waiting_for_sub_link, temp_user_id, temp_order_id
    parts = call.data.split("_")
    user_id = int(parts[1])
    order_id = int(parts[2])
    
    update_order_status(order_id, "approved")
    purchases = update_purchases(user_id)
    
    remaining = 5 - (purchases % 5)
    if remaining == 5:
        remaining = 0
    gift_msg = f"\n\n🎁 تبریک! شما یک اشتراک هدیه دریافت کردید! 🎁\n(هر ۵ خرید یک هدیه)" if purchases % 5 == 0 else ""
    
    waiting_for_sub_link = True
    temp_user_id = user_id
    temp_order_id = order_id
    
    bot.answer_callback_query(call.id, "✅ تایید شد")
    bot.send_message(ADMIN_ID, f"✅ سفارش #{order_id} کاربر {user_id} تایید شد.\n📊 تعداد خرید کاربر: {purchases}\n🎁 تا هدیه بعدی: {remaining} خرید{gift_msg}\n\n📎 لینک ساب را ارسال کنید:")
    bot.send_message(user_id, f"✅ سفارش شما تایید شد!{gift_msg}\n\n⏳ لینک اشتراک در حال ارسال است...")

@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_"))
def reject_callback(call):
    parts = call.data.split("_")
    user_id = int(parts[1])
    order_id = int(parts[2])
    
    update_order_status(order_id, "rejected")
    bot.answer_callback_query(call.id, "❌ رد شد")
    bot.send_message(user_id, "❌ سفارش شما رد شد.\nلطفاً با پشتیبانی تماس بگیرید.")
    if user_id in user_plans:
        del user_plans[user_id]

# ================= PHOTO RECEIPT =================
@bot.message_handler(content_types=['photo'])
def receipt_photo(msg):
    if not bot_active and msg.from_user.id != ADMIN_ID:
        bot.send_message(msg.chat.id, "⚠️ با عرض پوزش، سرور در حال بروزرسانی میباشد. لطفا بعدا مراجعه کنید.")
        return
    uid = msg.from_user.id
    if uid not in waiting_for_receipt:
        bot.send_message(uid, "❌ ابتدا روی «پرداخت کردم» کلیک کنید.")
        return
    if uid not in user_plans:
        bot.send_message(uid, "❌ خطا! لطفاً دوباره پلن را انتخاب کنید.")
        waiting_for_receipt.discard(uid)
        return
    
    photo = msg.photo[-1].file_id
    plan = user_plans[uid]
    username = msg.from_user.username or "بدون نام"
    
    caption = f"🆕 سفارش جدید\n👤 کاربر: {uid}\n📝 @{username}\n📦 {plan['plan']}\n💰 {plan['price']} تومان\n🆔 #{plan['order_id']}"
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ تایید", callback_data=f"approve_{uid}_{plan['order_id']}"),
        types.InlineKeyboardButton("❌ رد", callback_data=f"reject_{uid}_{plan['order_id']}")
    )
    
    bot.send_photo(ADMIN_ID, photo, caption=caption, reply_markup=markup)
    waiting_for_receipt.discard(uid)
    bot.send_message(uid, "✅ رسید شما دریافت شد.\n⏳ در حال بررسی توسط ادمین...")

# ================= SEND SUB LINK =================
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and waiting_for_sub_link == True)
def send_sub_link(msg):
    global waiting_for_sub_link, temp_user_id, temp_order_id
    
    sub_link = msg.text.strip()
    
    if not sub_link or len(sub_link) < 5:
        bot.send_message(ADMIN_ID, "❌ لینک معتبر نیست! دوباره ارسال کنید:")
        return
    
    update_order_status(temp_order_id, "completed", sub_link)
    purchases = get_purchases(temp_user_id)
    remaining = 5 - (purchases % 5)
    if remaining == 5:
        remaining = 0
    
    text = f"""
🎉 اشتراک شما فعال شد! 🎉

━━━━━━━━━━━━━━━━━━━━
📋 کپی لینک ساب:

<code>{sub_link}</code>
━━━━━━━━━━━━━━━━━━━━
🔗 برای مشاهده جزئیات روی لینک زیر کلیک کنید:

{sub_link}
━━━━━━━━━━━━━━━━━━━━

🎁 تا هدیه بعدی: {remaining} خرید دیگر

━━━━━━━━━━━━━━━━━━━━
📱 آموزش اتصال (اندروید):
1️⃣ اپ V2RayNG یا Hiddify را نصب کنید.
2️⃣ روی Import From Clipboard کلیک کنید.
3️⃣ دکمه Connect را بزنید.

🍏 آموزش اتصال (iOS):
1️⃣ اپ Hiddify یا Streisand را نصب کنید.
2️⃣ گزینه Add Subscription را انتخاب کنید.
3️⃣ لینک بالا را Paste کرده و Save کنید.
4️⃣ Connect را بزنید.

📺 ویدیو آموزش اتصال: @Mig_Mig_Vpn1
━━━━━━━━━━━━━━━━━━━━

📞 پشتیبانی: @Mig_Mig_Vpn2
"""
    
    try:
        bot.send_message(temp_user_id, text, parse_mode="HTML")
        bot.send_message(ADMIN_ID, f"✅ لینک ساب به کاربر {temp_user_id} ارسال شد.", reply_markup=admin_keyboard())
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ خطا در ارسال: {e}")
    
    waiting_for_sub_link = False
    if temp_user_id in user_plans:
        del user_plans[temp_user_id]

# ================= SEND MESSAGES =================
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and waiting_for_sub_link == "ask_user_id")
def ask_user_id(msg):
    global waiting_for_sub_link, temp_user_id
    try:
        temp_user_id = int(msg.text.strip())
        waiting_for_sub_link = "send_msg"
        bot.send_message(ADMIN_ID, "📝 متن پیام را وارد کنید:")
    except:
        bot.send_message(ADMIN_ID, "❌ ID نامعتبر!")
        waiting_for_sub_link = False

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and waiting_for_sub_link == "send_msg")
def send_private_msg(msg):
    global waiting_for_sub_link, temp_user_id
    try:
        bot.send_message(temp_user_id, f"📢 پیام از ادمین:\n\n{msg.text}")
        bot.send_message(ADMIN_ID, f"✅ پیام به کاربر {temp_user_id} ارسال شد.")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ خطا در ارسال: {e}")
    waiting_for_sub_link = False

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and waiting_for_sub_link == "broadcast")
def send_broadcast(msg):
    global waiting_for_sub_link
    users = get_all_users()
    sent = 0
    bot.send_message(ADMIN_ID, "⏳ در حال ارسال پیام همگانی...")
    for uid, _, _, _ in users:
        try:
            bot.send_message(uid, f"📢 پیام همگانی:\n\n{msg.text}")
            sent += 1
            time.sleep(0.05)
        except:
            pass
    bot.send_message(ADMIN_ID, f"✅ پیام همگانی ارسال شد.\n📨 ارسال شده به {sent} کاربر.")
    waiting_for_sub_link = False

# ================= DEFAULT =================
@bot.message_handler(func=lambda m: True)
def default(msg):
    if msg.from_user.id != ADMIN_ID:
        if not bot_active:
            bot.send_message(msg.chat.id, "⚠️ با عرض پوزش، سرور در حال بروزرسانی میباشد. لطفا بعدا مراجعه کنید.")
        else:
            bot.send_message(msg.chat.id, "لطفاً از دکمه‌های منو استفاده کنید 👇", 
                             reply_markup=main_keyboard(msg.from_user.id))
    else:
        # اگر ادمین پیام متنی غیر از دکمه‌ها بفرستد، نادیده گرفته می‌شود
        pass

# ================= RUN =================
if __name__ == "__main__":
    print("🚀 ربات در حال اجراست...")
    init_db()
    
    # حذف Webhook برای جلوگیری از تداخل با Polling
    bot.remove_webhook()
    print("✅ Webhook حذف شد. ربات با Polling اجرا می‌شود.")
    
    bot.infinity_polling()
