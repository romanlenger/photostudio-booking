"""
Telegram bot with additional services system
"""
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal
from app.models import Booking, Client

# Bot config
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    try:
        with open("bot_token.txt", "r") as f:
            BOT_TOKEN = f.read().strip()
    except:
        raise ValueError("BOT_TOKEN not found!")

ADMIN_IDS_STR = os.getenv("ADMIN_IDS") or os.getenv("TELEGRAM_ADMIN_CHAT_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]

STUDIO_RULES = os.getenv("STUDIO_RULES")

# Website and social media URLs
WEBSITE_URL = os.getenv("WEBSITE_URL", "http://192.168.88.26:8000")
INSTAGRAM_URL = os.getenv("INSTAGRAM_URL", "https://instagram.com/clique_studio")

def get_db():
    return SessionLocal()

def get_main_keyboard():
    """Постійна клавіатура з сайтом та Instagram (завжди)"""
    keyboard = [
        [KeyboardButton("🌐 Перейти на сайт"), KeyboardButton("📸 Instagram")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    """Клавіатура з кнопкою скасування + основні кнопки (під час бронювання)"""
    keyboard = [
        [KeyboardButton("❌ Скасувати бронювання")],
        [KeyboardButton("🌐 Перейти на сайт"), KeyboardButton("📸 Instagram")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def remove_keyboard():
    """Remove keyboard"""
    return ReplyKeyboardRemove()

async def notify_admins(context, message):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message, parse_mode='HTML')
        except: pass

def calculate_price(people, zone, animals, bg):
    price = 1000
    if people > 4: price += (people - 4) * 100
    if zone == 'both': price += 500
    if animals > 1: price += (animals - 1) * 100
    if bg != 'none': price += 100
    return price

def format_services(people, zone, animals, bg, price):
    zones = {'light': 'Світла', 'dark': 'Темна', 'both': 'Обидві (+500₴)'}
    bgs = {'none': 'Без фону', 'white': 'Білий (+100₴)', 'black': 'Чорний (+100₴)', 'red': 'Червоний (+100₴)'}
    p_txt = f"До 4 осіб" if people <= 4 else f"{people} осіб (+{(people-4)*100}₴)"
    a_txt = "Немає" if animals == 0 else (f"1 тварина" if animals == 1 else f"{animals} (+{(animals-1)*100}₴)")
    return f"""📋 <b>Обрані послуги:</b>

👥 Людей: {p_txt}
📸 Зона: {zones.get(zone, zone)}
🐾 Тварини: {a_txt}
🎨 Фон: {bgs.get(bg, bg)}

💰 <b>Сума: {price} грн</b>"""

async def start(update, context):
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        await update.message.reply_text("👋 Вітаю, адміне!")
        return
    if context.args and context.args[0].startswith("booking_"):
        booking_id = context.args[0].replace("booking_", "")
        await handle_booking(update, context, booking_id)
    else:
        await update.message.reply_text(
            "👋 Вітаємо в CLIQUE!\n\n🌐 http://192.168.88.26:8000",
            reply_markup=get_main_keyboard()
        )

async def handle_booking(update, context, booking_id):
    user_id = update.effective_user.id
    username = update.effective_user.username or "без username"
    db = get_db()
    try:
        booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
        if not booking:
            await update.message.reply_text("❌ Бронювання не знайдено")
            return
        client = db.query(Client).filter(Client.id == booking.client_id).first()
        if booking.status in ['confirmed', 'paid']:
            await update.message.reply_text(f"✅ Вже підтверджено!\n📅 {booking.booking_date.strftime('%d.%m.%Y')} {booking.booking_hour}:00")
            return
        booking.telegram_user_id = user_id
        db.commit()
        
        text = f"""{STUDIO_RULES}

━━━━━━━━━━━━━━━━

📅 <b>Бронювання:</b>
Дата: {booking.booking_date.strftime('%d.%m.%Y')}
Час: {booking.booking_hour}:00
Ім'я: {client.name}
Телефон: {client.phone}

━━━━━━━━━━━━━━━━

❓ Підтверджуєте?"""
        
        keyboard = [[
            InlineKeyboardButton("✅ Так", callback_data=f"confirm_{booking_id}"),
            InlineKeyboardButton("❌ Ні", callback_data=f"cancel_{booking_id}")
        ]]
        
        # Додаємо постійну клавіатуру зі скасуванням
        sent = await update.message.reply_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='HTML'
        )
        
        # Відправляємо окреме повідомлення з постійною клавіатурою
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="💡 <b>Корисні кнопки з'явились внизу:</b>\n\n"
                 "• ❌ Скасувати бронювання\n"
                 "• 🌐 Перейти на сайт\n"
                 "• 📸 Наш Instagram",
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        
        booking.confirmation_message_id = sent.message_id
        db.commit()
        
        tg_info = f"@{username}" if username != "без username" else f"ID: {user_id}"
        await notify_admins(context, f"📬 <b>Нове бронювання</b>\n\nID: #{booking_id}\n👤 {client.name}\n📞 {client.phone}\n💬 {tg_info}\n📅 {booking.booking_date.strftime('%d.%m.%Y')} {booking.booking_hour}:00")
    finally:
        db.close()

async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("confirm_"):
        await start_services(query, context, data.replace("confirm_", ""))
    elif data.startswith("cancel_"):
        await cancel_booking(query, context, data.replace("cancel_", ""))
    elif data.startswith("people_"):
        await handle_people(query, context)
    elif data.startswith("zone_"):
        await handle_zone(query, context)
    elif data.startswith("animals_"):
        await handle_animals(query, context)
    elif data.startswith("bg_"):
        await handle_bg(query, context)
    elif data.startswith("copy_card_"):
        # Показати номер картки для копіювання
        card_number = "5168757412345678"
        await query.answer(f"📋 Номер картки: {card_number}", show_alert=True)
    elif data.startswith("copy_purpose_"):
        # Показати призначення платежу
        parts = data.split("_")
        if len(parts) >= 5:
            date_str = parts[3]  # YYYYMMDD
            hour = parts[4]
            # Форматуємо дату
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')
            purpose = f"Бронювання {formatted_date} {hour}:00"
            await query.answer(f"📝 Призначення: {purpose}", show_alert=True)


async def start_services(query, context, booking_id):
    context.user_data['booking_id'] = booking_id
    context.user_data['people'] = 4
    context.user_data['zone'] = None
    context.user_data['animals'] = 0
    context.user_data['bg'] = None
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_text(query.message.text + "\n\n✅ <b>ПІДТВЕРДЖЕНО</b>", parse_mode='HTML')
    except: pass
    
    keyboard = [[InlineKeyboardButton("👥 До 4", callback_data="people_up4")],
                [InlineKeyboardButton("👥 Більше", callback_data="people_more")]]
    await context.bot.send_message(query.message.chat_id, "<b>1/4: Кількість людей</b>\n\nДо 4 - без доплат\nБільше - 100₴/особа", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_people(query, context):
    if query.data == "people_up4":
        context.user_data['people'] = 4
        await query.answer("✅ До 4 осіб")
        await ask_zone(query, context)
    else:
        await query.edit_message_text("👥 Введіть кількість (5-20):", parse_mode='HTML')
        context.user_data['waiting'] = 'people'

async def handle_text(update, context):
    text = update.message.text.strip()
    
    # Перевірка на кнопки меню
    if text == "❌ Скасувати бронювання":
        await handle_cancel_button(update, context)
        return
    elif text == "🌐 Перейти на сайт":
        await update.message.reply_text(
            f"🌐 <b>Сайт фотостудії CLIQUE</b>\n\n"
            f"Тут ви можете:\n"
            f"• Переглянути календар\n"
            f"• Створити нове бронювання\n"
            f"• Обрати зручний час\n\n"
            f"👉 {WEBSITE_URL}",
            parse_mode='HTML'
        )
        return
    elif text == "📸 Instagram":
        await update.message.reply_text(
            f"📸 <b>Наш Instagram</b>\n\n"
            f"Підписуйтесь на нас:\n"
            f"• Фото з фотосесій\n"
            f"• Новини студії\n"
            f"• Спеціальні пропозиції\n\n"
            f"👉 {INSTAGRAM_URL}",
            parse_mode='HTML'
        )
        return
    
    if 'waiting' not in context.user_data: return
    waiting = context.user_data['waiting']
    try:
        num = int(text)
        if waiting == 'people':
            if num < 5 or num > 20:
                await update.message.reply_text("❌ Від 5 до 20")
                return
            context.user_data['people'] = num
            await update.message.reply_text(f"✅ {num} осіб (+{(num-4)*100}₴)")
            del context.user_data['waiting']
            class FQ: 
                def __init__(self, m): self.message = m
            await ask_zone(FQ(update.message), context)
        elif waiting == 'animals':
            if num < 2 or num > 10:
                await update.message.reply_text("❌ Від 2 до 10")
                return
            context.user_data['animals'] = num
            await update.message.reply_text(f"✅ {num} тварини (+{(num-1)*100}₴)")
            del context.user_data['waiting']
            class FQ:
                def __init__(self, m): self.message = m
            await ask_bg(FQ(update.message), context)
    except ValueError:
        await update.message.reply_text("❌ Введіть число")

async def ask_zone(query, context):
    keyboard = [[InlineKeyboardButton("☀️ Світла", callback_data="zone_light")],
                [InlineKeyboardButton("🌙 Темна", callback_data="zone_dark")],
                [InlineKeyboardButton("✨ Обидві (+500₴)", callback_data="zone_both")]]
    await context.bot.send_message(query.message.chat_id, "<b>2/4: Фотозона</b>\n\nОбидві - доплата 500₴", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_zone(query, context):
    choice = query.data.replace("zone_", "")
    context.user_data['zone'] = choice
    names = {'light': 'Світла', 'dark': 'Темна', 'both': 'Обидві'}
    await query.answer(f"✅ {names[choice]}")
    await ask_animals(query, context)

async def ask_animals(query, context):
    keyboard = [[InlineKeyboardButton("🚫 Немає", callback_data="animals_none")],
                [InlineKeyboardButton("🐾 1 тварина", callback_data="animals_one")],
                [InlineKeyboardButton("🐾🐾 Більше", callback_data="animals_more")]]
    await context.bot.send_message(query.message.chat_id, "<b>3/4: Тварини</b>\n\n1 - безкоштовно\nБільше - 100₴/тварина", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_animals(query, context):
    if query.data == "animals_none":
        context.user_data['animals'] = 0
        await query.answer("✅ Без тварин")
        await ask_bg(query, context)
    elif query.data == "animals_one":
        context.user_data['animals'] = 1
        await query.answer("✅ 1 тварина")
        await ask_bg(query, context)
    else:
        await query.edit_message_text("🐾 Введіть кількість (2-10):", parse_mode='HTML')
        context.user_data['waiting'] = 'animals'

async def ask_bg(query, context):
    keyboard = [[InlineKeyboardButton("🚫 Без фону", callback_data="bg_none")],
                [InlineKeyboardButton("⚪ Білий (+100₴)", callback_data="bg_white")],
                [InlineKeyboardButton("⚫ Чорний (+100₴)", callback_data="bg_black")],
                [InlineKeyboardButton("🔴 Червоний (+100₴)", callback_data="bg_red")]]
    await context.bot.send_message(query.message.chat_id, "<b>4/4: Фон</b>\n\nБудь-який - 100₴", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_bg(query, context):
    choice = query.data.replace("bg_", "")
    context.user_data['bg'] = choice
    await finalize(query, context)

async def finalize(query, context):
    bid = context.user_data.get('booking_id')
    people = context.user_data.get('people', 4)
    zone = context.user_data.get('zone', 'light')
    animals = context.user_data.get('animals', 0)
    bg = context.user_data.get('bg', 'none')
    price = calculate_price(people, zone, animals, bg)
    
    db = get_db()
    try:
        booking = db.query(Booking).filter(Booking.id == int(bid)).first()
        client = db.query(Client).filter(Client.id == booking.client_id).first()
        booking.status = "confirmed"
        booking.people_count = people
        booking.zone_choice = zone
        booking.animals_count = animals
        booking.background_choice = bg
        booking.total_price = price
        db.commit()
        
        summary = format_services(people, zone, animals, bg, price)
        
        card_number = "UA833052990000026002000123966"  # Без пробілів для копіювання
        card_display = "UA833052990000026002000123966"  # З пробілами для читабельності
        purpose = f"Бронювання {booking.booking_date.strftime('%d.%m.%Y')} {booking.booking_hour}:00"
        
        payment = f"""✅ <b>Підтверджено!</b>

{summary}

━━━━━━━━━━━━━━━━

💳 <b>Реквізити:</b>

<code>{card_display}</code>
ФОП Кріпак Юлія Павлівна

<b>Сума: {price} грн</b>

Призначення:
<code>{purpose}</code>

📸 Після оплати надішліть скріншот

💡 Натисніть на номер картки або призначення щоб скопіювати"""
        
        # Додаємо кнопки для копіювання
        keyboard = [
            [InlineKeyboardButton("📋 Скопіювати картку", callback_data=f"copy_card_{booking.id}")],
            [InlineKeyboardButton("📝 Скопіювати призначення", callback_data=f"copy_purpose_{booking.id}_{booking.booking_date.strftime('%Y%m%d')}_{booking.booking_hour}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(query.message.chat_id, payment, reply_markup=reply_markup, parse_mode='HTML')
        
        # Нагадати про кнопки внизу
        await context.bot.send_message(
            query.message.chat_id,
            "💡 Корисні кнопки внизу:\n"
            "• ❌ Скасувати (якщо передумали)\n"
            "• 🌐 Сайт • 📸 Instagram"
        )
        
        username = query.from_user.username
        tg = f"@{username}" if username else f"ID: {query.from_user.id}"
        await notify_admins(context, f"✅ <b>Підтверджено</b>\n\nID: #{bid}\n👤 {client.name}\n📞 {client.phone}\n💬 {tg}\n📅 {booking.booking_date.strftime('%d.%m.%Y')} {booking.booking_hour}:00\n\n{summary}\n\n⏳ Чекаємо оплату...")
    finally:
        db.close()

async def handle_cancel_button(update, context):
    """Handle cancel button from persistent keyboard"""
    user_id = update.effective_user.id
    db = get_db()
    
    try:
        # Знайти активне бронювання користувача
        booking = db.query(Booking).filter(
            Booking.telegram_user_id == user_id,
            Booking.status.in_(['pending', 'confirmed'])
        ).first()
        
        if not booking:
            await update.message.reply_text(
                "ℹ️ У вас немає активних бронювань для скасування.",
                reply_markup=get_main_keyboard()
            )
            return
        
        # Отримати інфо про клієнта
        client = db.query(Client).filter(Client.id == booking.client_id).first()
        
        # Зберегти інфо
        booking_id = booking.id
        client_name = client.name
        client_phone = client.phone
        booking_date = booking.booking_date
        booking_hour = booking.booking_hour
        
        # Видалити з БД
        db.delete(booking)
        db.commit()
        
        # Повернути основні кнопки (без скасування)
        await update.message.reply_text(
            "❌ <b>Бронювання скасовано!</b>\n\n"
            f"📅 {booking_date.strftime('%d.%m.%Y')} о {booking_hour}:00\n\n"
            "Якщо передумаєте - створіть нове бронювання на сайті.",
            reply_markup=get_main_keyboard(),
            parse_mode='HTML'
        )
        
        # Очистити user_data
        context.user_data.clear()
        
        # Сповістити адмінів
        username = update.effective_user.username
        tg = f"@{username}" if username else f"ID: {user_id}"
        await notify_admins(
            context,
            f"❌ <b>Бронювання скасовано клієнтом</b>\n\n"
            f"ID: #{booking_id}\n"
            f"👤 {client_name}\n"
            f"📞 {client_phone}\n"
            f"💬 {tg}\n"
            f"📅 {booking_date.strftime('%d.%m.%Y')} {booking_hour}:00\n\n"
            f"⚠️ Скасовано через постійну кнопку"
        )
    
    finally:
        db.close()

async def cancel_booking(query, context, bid):
    db = get_db()
    try:
        booking = db.query(Booking).filter(Booking.id == int(bid)).first()
        if not booking:
            await query.answer("❌ Не знайдено")
            return
        client = db.query(Client).filter(Client.id == booking.client_id).first()
        name, phone = client.name, client.phone
        date, hour = booking.booking_date, booking.booking_hour
        db.delete(booking)
        db.commit()
        try:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.edit_message_text(query.message.text + "\n\n❌ <b>СКАСОВАНО</b>", parse_mode='HTML')
        except: pass
        
        await context.bot.send_message(
            query.message.chat_id, 
            "❌ Скасовано",
            reply_markup=get_main_keyboard()
        )
        
        # Очистити user_data
        context.user_data.clear()
        
        username = query.from_user.username
        tg = f"@{username}" if username else f"ID: {query.from_user.id}"
        await notify_admins(context, f"❌ <b>Скасовано</b>\n\nID: #{bid}\n👤 {name}\n📞 {phone}\n💬 {tg}\n📅 {date.strftime('%d.%m.%Y')} {hour}:00")
    finally:
        db.close()

async def handle_photo(update, context):
    user_id = update.effective_user.id
    db = get_db()
    try:
        booking = db.query(Booking).filter(Booking.telegram_user_id == user_id, Booking.status == 'confirmed').first()
        if booking:
            client = db.query(Client).filter(Client.id == booking.client_id).first()
            booking.status = "paid"
            db.commit()
            
            # Повернути основні кнопки після оплати
            await update.message.reply_text(
                "✅ Квитанцію отримано!\n\nОплата буде перевірена.\n\n"
                "Дякуємо за бронювання! 🎉",
                reply_markup=get_main_keyboard()
            )
            
            # Очистити user_data
            context.user_data.clear()
            
            services = ""
            if booking.total_price and booking.total_price > 1000:
                services = f"\n\n{format_services(booking.people_count or 4, booking.zone_choice or 'light', booking.animals_count or 0, booking.background_choice or 'none', booking.total_price)}"
            
            username = update.effective_user.username
            tg = f"@{username}" if username else f"ID: {user_id}"
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.forward_message(admin_id, update.message.chat_id, update.message.message_id)
                    await context.bot.send_message(admin_id, f"💰 <b>Квитанція</b>\n\nID: #{booking.id}\n👤 {client.name}\n📞 {client.phone}\n💬 {tg}\n📅 {booking.booking_date.strftime('%d.%m.%Y')} {booking.booking_hour}:00{services}\n\n❗️ Перевірте!", parse_mode='HTML')
                except: pass
        else:
            await update.message.reply_text(
                "ℹ️ Спочатку створіть бронювання на сайті",
                reply_markup=get_main_keyboard()
            )
    finally:
        db.close()

async def help_cmd(update, context):
    await update.message.reply_text(
        "ℹ️ <b>Довідка</b>\n\n1. Бронюйте на сайті\n2. Підтвердіть тут\n3. Оберіть послуги\n4. Оплатіть\n5. Надішліть квитанцію", 
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print(f"🤖 Bot started! Admins: {ADMIN_IDS}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
