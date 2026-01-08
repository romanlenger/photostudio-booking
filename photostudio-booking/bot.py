"""
Simplified Telegram Bot v2.0
All services selected on website - bot only confirms and receives payment
"""
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from datetime import datetime
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal
from app.models import Booking, Client
from monobank import monobank

# ========== CONFIGURATION ==========

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    try:
        with open("bot_token.txt", "r") as f:
            BOT_TOKEN = f.read().strip()
    except:
        raise ValueError("BOT_TOKEN not found!")

ADMIN_IDS_STR = os.getenv("ADMIN_IDS") or os.getenv("TELEGRAM_ADMIN_CHAT_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]

# NEW: Photographer ID for notifications when studio photographer is selected
PHOTOGRAPHER_ID_STR = os.getenv("PHOTOGRAPHER_ID", "")
PHOTOGRAPHER_ID = int(PHOTOGRAPHER_ID_STR) if PHOTOGRAPHER_ID_STR.strip() else None

STUDIO_RULES = os.getenv("STUDIO_RULES") or """📋 Правила фотостудії CLIQUE:

1. Приходьте вчасно
2. До 4 осіб без доплат
3. За пошкодження обладнання - відповідальність клієнта
4. Заборонено курити
5. 1 тварина без доплати

⚠️ При скасуванні <24 год - передоплата не повертається"""

WEBSITE_URL = os.getenv("WEBSITE_URL", "http://192.168.88.26:8000")
INSTAGRAM_URL = os.getenv("INSTAGRAM_URL", "https://instagram.com/clique_studio")

# Payment details
CARD_NUMBER = "UA833052990000026002000123966"
CARD_DISPLAY = "UA833052990000026002000123966"
CARDHOLDER_NAME = "Кріпак Юлія Павлівна"

# ========== DATABASE ==========

def get_db():
    return SessionLocal()

# ========== KEYBOARDS ==========

def get_main_keyboard():
    """Main keyboard (always visible)"""
    keyboard = [
        [KeyboardButton("🌐 Перейти на сайт"), KeyboardButton("📸 Instagram")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    """Keyboard with cancel button (during booking)"""
    keyboard = [
        [KeyboardButton("❌ Скасувати бронювання")],
        [KeyboardButton("🌐 Перейти на сайт"), KeyboardButton("📸 Instagram")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ========== HELPER FUNCTIONS ==========

async def notify_admins(context, message):
    """Send message to all admins"""
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message, parse_mode='HTML')
        except:
            pass

async def notify_photographer(context, message):
    """Send message to photographer (only if photographer_choice = 'studio')"""
    if PHOTOGRAPHER_ID:
        try:
            await context.bot.send_message(chat_id=PHOTOGRAPHER_ID, text=message, parse_mode='HTML')
        except:
            pass

def format_hours_display(hours):
    """
    Format hours for display
    [14, 15, 16] → "14:00-17:00"
    [14, 17] → "14:00, 17:00"
    """
    if not hours:
        return ""
    if len(hours) == 1:
        return f"{hours[0]}:00"
    
    hours = sorted(hours)
    is_consecutive = all(hours[i] == hours[i-1] + 1 for i in range(1, len(hours)))
    
    if is_consecutive:
        return f"{hours[0]}:00-{hours[-1] + 1}:00"
    else:
        return ", ".join(f"{h}:00" for h in hours)

def format_services_summary(booking):
    """Format services for display"""
    zones = {'light': '☀️ Світла', 'dark': '🌙 Темна', 'both': '✨ Обидві'}
    bgs = {'none': 'Без фону', 'white': '⚪ Білий', 'black': '⚫ Чорний', 'red': '🔴 Червоний'}
    photographers = {'client': '🙋 Ваш фотограф', 'studio': '👨‍💼 Наш фотограф'}
    
    people_text = f"{booking.people_count} осіб" if booking.people_count <= 4 else f"{booking.people_count} осіб (+{(booking.people_count-4)*100}₴)"
    animals_text = "Немає" if booking.animals_count == 0 else (f"{booking.animals_count}" if booking.animals_count == 1 else f"{booking.animals_count} (+{(booking.animals_count-1)*100}₴)")
    
    summary = f"""📋 <b>Обрані послуги:</b>

👥 Людей: {people_text}
📸 Зона: {zones.get(booking.zone_choice, booking.zone_choice)}
🐾 Тварини: {animals_text}
🎨 Фон: {bgs.get(booking.background_choice, booking.background_choice)}
📷 Фотограф: {photographers.get(booking.photographer_choice, booking.photographer_choice)}

💰 <b>Загальна сума: {booking.total_price} грн</b>"""
    
    return summary

# ========== HANDLERS ==========

async def start(update: Update, context):
    """Handle /start command"""
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        await update.message.reply_text("👋 Вітаю, адміне!")
        return
    
    # Check if it's a booking deep link
    if context.args and context.args[0].startswith("booking_"):
        booking_id = int(context.args[0].replace("booking_", ""))
        await handle_booking_confirmation(update, context, booking_id)
    else:
        await update.message.reply_text(
            f"👋 Вітаємо в CLIQUE!\n\n🌐 Забронювати: {WEBSITE_URL}",
            reply_markup=get_main_keyboard()
        )

async def handle_booking_confirmation(update: Update, context, first_booking_id):
    """Show booking for confirmation - ALL SERVICES ALREADY SELECTED ON WEBSITE!"""
    db = get_db()
    
    try:
        # Get first booking to find group
        first_booking = db.query(Booking).filter(Booking.id == first_booking_id).first()
        
        if not first_booking:
            await update.message.reply_text("❌ Бронювання не знайдено")
            return
        
        # Get all bookings in this group
        group_id = first_booking.booking_group_id
        
        if group_id:
            # Multiple hours booking
            bookings = db.query(Booking).filter(
                Booking.booking_group_id == group_id
            ).order_by(Booking.booking_hour).all()
        else:
            # Single hour booking (backward compatibility)
            bookings = [first_booking]
        
        # Get client info
        client = db.query(Client).filter(Client.id == first_booking.client_id).first()
        
        # Collect all hours
        hours = [b.booking_hour for b in bookings]
        hours_display = format_hours_display(hours)
        
        # Format services summary (from website!)
        services_summary = format_services_summary(first_booking)
        
        # Check if discount applied (3+ hours)
        discount_info = ""
        if len(hours) >= 3:
            discount_info = "\n🎉 <b>Застосовано знижку 10%!</b>"
        
        # Build confirmation message
        message = f"""{STUDIO_RULES}

━━━━━━━━━━━━━━━━

📅 <b>Ваше бронювання:</b>

📆 Дата: {first_booking.booking_date.strftime('%d.%m.%Y')}
🕐 Години: {hours_display} ({len(hours)} год)
👤 Ім'я: {client.name}
📞 Телефон: {client.phone}

{services_summary}{discount_info}

━━━━━━━━━━━━━━━━

❓ Підтверджуєте бронювання?"""
        
        # Store user_id in ALL bookings of the group
        for booking in bookings:
            booking.telegram_user_id = update.effective_user.id
        db.commit()
        
        # Confirmation buttons
        keyboard = [[
            InlineKeyboardButton("✅ Так, підтверджую", callback_data=f"confirm_{first_booking_id}"),
            InlineKeyboardButton("❌ Скасувати", callback_data=f"cancel_{first_booking_id}")
        ]]
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
    finally:
        db.close()

async def button_callback(update: Update, context):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("confirm_"):
        booking_id = int(data.replace("confirm_", ""))
        await confirm_booking(query, context, booking_id)
    
    elif data.startswith("cancel_"):
        booking_id = int(data.replace("cancel_", ""))
        await cancel_booking(query, context, booking_id)
    
    elif data.startswith("copy_card"):
        await query.answer(f"📋 Номер картки: {CARD_NUMBER}", show_alert=True)
    
    elif data.startswith("copy_purpose_"):
        # Extract booking info from callback data
        parts = data.split("_")
        if len(parts) >= 4:
            date_str = parts[2]
            hours_str = parts[3]
            
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')
            
            purpose = f"Бронювання {formatted_date} {hours_str}"
            await query.answer(f"📝 Призначення: {purpose}", show_alert=True)

    elif data.startswith("pay_online_"):
        booking_id = int(data.split("_")[2])
        await handle_pay_online(query, context, booking_id)
    
    elif data.startswith("pay_manual_"):
        booking_id = int(data.split("_")[2])
        await handle_pay_manual(query, context, booking_id)
    
    elif data.startswith("back_to_payment_"):
        booking_id = int(data.split("_")[3])
        await handle_back_to_payment(query, context, booking_id)


async def confirm_booking(query, context, first_booking_id):
    """Confirm booking and show payment details"""
    db = get_db()
    
    try:
        # Get first booking
        first_booking = db.query(Booking).filter(Booking.id == first_booking_id).first()
        
        if not first_booking:
            await query.edit_message_text("❌ Бронювання не знайдено")
            return
        
        # Get all bookings in group
        group_id = first_booking.booking_group_id
        
        if group_id:
            bookings = db.query(Booking).filter(
                Booking.booking_group_id == group_id
            ).all()
        else:
            bookings = [first_booking]
        
        # Update status to confirmed
        for booking in bookings:
            booking.status = 'confirmed'
        db.commit()
        
        # Get client
        client = db.query(Client).filter(Client.id == first_booking.client_id).first()
        
        # Collect hours
        hours = sorted([b.booking_hour for b in bookings])
        hours_display = format_hours_display(hours)
        
        # Format services
        services_summary = format_services_summary(first_booking)
        
        # Check discount
        discount_info = ""
        if len(hours) >= 3:
            discount_info = "\n🎉 <i>Знижка 10% вже застосована!</i>"
        
        # Payment purpose
        purpose = f"Бронювання {first_booking.booking_date.strftime('%d.%m.%Y')} {hours_display}"
        
        # Photographer contact info
        photographer_contact = ""
        if first_booking.photographer_choice == 'studio':
            photographer_contact = "\n\n💬 <b>Зв'язатись з фотографом для обговорення ідеї:</b> @lonkilin"
        
        # Payment message
        payment_message = f"""✅ <b>Підтверджено!</b>

{services_summary}{discount_info}

━━━━━━━━━━━━━━━━

💳 <b>Оберіть спосіб оплати:</b>

<b>Сума: {first_booking.total_price} грн</b>

━━━━━━━━━━━━━━━━

💡 <b>Онлайн-оплата:</b>
- Миттєве підтвердження
- Картою будь-якого банку
- Google Pay / Apple Pay

📋 <b>Реквізити:</b>
- Тільки для фізичних осіб
- Підтвердження після скріншоту{photographer_contact}"""
        
        # Copy buttons + Contract button
        date_str = first_booking.booking_date.strftime('%Y%m%d')
        keyboard = [
            [InlineKeyboardButton("💳 Оплата карткою (Google Pay, Apple Pay)", callback_data=f"pay_online_{first_booking_id}")],
            [InlineKeyboardButton("📋 Оплата на реквізити", callback_data=f"pay_manual_{first_booking_id}")],
            [InlineKeyboardButton("📄 Договір публічної оферти", url=f"{WEBSITE_URL}/static/contract.html")]
        ]
        
        # Update original message
        try:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.edit_message_text(
                query.message.text + "\n\n✅ <b>ПІДТВЕРДЖЕНО</b>",
                parse_mode='HTML'
            )
        except:
            pass
        
        # Send payment details
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=payment_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
        # Show cancel keyboard
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="💡 Корисні кнопки з'явились внизу",
            reply_markup=get_cancel_keyboard()
        )
        
        # Notify admins
        username = query.from_user.username
        tg = f"@{username}" if username else f"ID: {query.from_user.id}"
        
        admin_message = f"""✅ <b>Нове підтверджене бронювання</b>

ID: #{first_booking_id}
👤 {client.name}
📞 {client.phone}
💬 {tg}

📅 {first_booking.booking_date.strftime('%d.%m.%Y')}
🕐 {hours_display} ({len(hours)} год)

{services_summary}

⏳ Чекаємо оплату..."""
        
        await notify_admins(context, admin_message)
        
        # NEW: Notify photographer if studio photographer selected
        if first_booking.photographer_choice == 'studio':
            photographer_message = f"""📸 <b>Нова фотосесія для вас!</b>

📅 Дата: {first_booking.booking_date.strftime('%d.%m.%Y')}
🕐 Час: {hours_display} ({len(hours)} год)

👤 Клієнт: {client.name}
📞 Телефон: {client.phone}

📋 <b>Деталі:</b>
{services_summary}

⏳ Чекаємо оплату від клієнта...

💡 Після оплати ви отримаєте фінальне підтвердження."""
            
            await notify_photographer(context, photographer_message)
        
    finally:
        db.close()


async def handle_pay_online(query, context, booking_id):
    """Handle online payment via Monobank"""
    db = get_db()
    
    try:
        # Get booking
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        
        if not booking:
            await query.edit_message_text("❌ Бронювання не знайдено")
            return
        
        # Get all bookings in group
        group_id = booking.booking_group_id
        if group_id:
            bookings = db.query(Booking).filter(
                Booking.booking_group_id == group_id
            ).all()
        else:
            bookings = [booking]
        
        # Get client
        client = db.query(Client).filter(Client.id == booking.client_id).first()
        
        # Collect hours
        hours = sorted([b.booking_hour for b in bookings])
        hours_display = format_hours_display(hours)
        
        # Create description
        description = f"Бронювання {booking.booking_date.strftime('%d.%m.%Y')} {hours_display}"
        
        # Create invoice in Monobank
        try:
            invoice_data = await monobank.create_invoice(
                amount=booking.total_price,
                booking_id=booking_id,
                client_name=client.name,
                description=description
            )
            
            # Save invoice ID to booking
            booking.monobank_invoice_id = invoice_data['invoiceId']
            booking.payment_method = 'online'
            db.commit()
            
            # Send payment link
            payment_url = invoice_data['pageUrl']
            
            message = f"""💳 <b>Рахунок створено!</b>

<b>Сума: {booking.total_price} грн</b>
Дійсний: 24 години

Після оплати бронювання підтвердиться автоматично!

💡 Можна платити карткою будь-якого банку України"""
            
            keyboard = [
                [InlineKeyboardButton("🔗 Перейти до оплати", url=payment_url)],
                [InlineKeyboardButton("◀️ Назад до вибору оплати", callback_data=f"back_to_payment_{booking_id}")]
            ]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            # Notify admins
            username = query.from_user.username
            tg = f"@{username}" if username else f"ID: {query.from_user.id}"
            
            admin_message = f"""💳 <b>Створено онлайн-рахунок</b>

ID: #{booking_id}
👤 {client.name}
📞 {client.phone}
💬 {tg}

📅 {booking.booking_date.strftime('%d.%m.%Y')}
🕐 {hours_display} ({len(hours)} год)

💰 Сума: {booking.total_price} грн

⏳ Очікуємо оплату через Monobank..."""
            
            await notify_admins(context, admin_message)
            
        except Exception as e:
            error_message = f"""❌ <b>Помилка створення рахунку</b>

Виникла технічна помилка при створенні рахунку.

Будь ласка, спробуйте:
- Оплату на реквізити
- Або напишіть нам: @clique_admin

Помилка: {str(e)}"""
            
            keyboard = [
                [InlineKeyboardButton("📋 Оплата на реквізити", callback_data=f"pay_manual_{booking_id}")],
                [InlineKeyboardButton("💬 Написати підтримку", url="https://t.me/clique_admin")]
            ]
            
            await query.edit_message_text(
                error_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            # Notify admins about error
            await notify_admins(context, f"⚠️ Помилка Monobank для бронювання #{booking_id}: {str(e)}")
    
    finally:
        db.close()


async def handle_pay_manual(query, context, booking_id):
    """Handle manual payment via bank transfer"""
    db = get_db()
    
    try:
        # Get booking
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        
        if not booking:
            await query.edit_message_text("❌ Бронювання не знайдено")
            return
        
        # Get all bookings in group
        group_id = booking.booking_group_id
        if group_id:
            bookings = db.query(Booking).filter(
                Booking.booking_group_id == group_id
            ).all()
        else:
            bookings = [booking]
        
        # Collect hours
        hours = sorted([b.booking_hour for b in bookings])
        hours_display = format_hours_display(hours)
        
        # Payment purpose
        purpose = f"Бронювання {booking.booking_date.strftime('%d.%m.%Y')} {hours_display}"
        
        # Update payment method
        booking.payment_method = 'manual'
        db.commit()
        
        # Manual payment message
        date_str = booking.booking_date.strftime('%Y%m%d')
        
        payment_message = f"""💳 <b>Реквізити для оплати:</b>

<code>{CARD_DISPLAY}</code>
{CARDHOLDER_NAME}

<b>Сума: {booking.total_price} грн</b>

Призначення:
<code>{purpose}</code>

⚠️ <b>Оплата за реквізитами тільки для фіз. осіб!</b>

━━━━━━━━━━━━━━━━

📸 <b>Після оплати надішліть скріншот квитанції в цей чат</b>

💡 Натисніть на номер картки або призначення щоб скопіювати"""
        
        # Copy buttons
        keyboard = [
            [InlineKeyboardButton("📋 Скопіювати картку", callback_data="copy_card")],
            [InlineKeyboardButton("📝 Скопіювати призначення", callback_data=f"copy_purpose_{date_str}_{hours_display.replace(':', '')}")],
            [InlineKeyboardButton("◀️ Назад до вибору оплати", callback_data=f"back_to_payment_{booking_id}")]
        ]
        
        await query.edit_message_text(
            payment_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    finally:
        db.close()


async def handle_back_to_payment(query, context, booking_id):
    """Go back to payment selection"""
    db = get_db()
    
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        
        if not booking:
            await query.edit_message_text("❌ Бронювання не знайдено")
            return
        
        # Get all bookings in group
        group_id = booking.booking_group_id
        if group_id:
            bookings = db.query(Booking).filter(
                Booking.booking_group_id == group_id
            ).all()
        else:
            bookings = [booking]
        
        # Collect hours
        hours = sorted([b.booking_hour for b in bookings])
        hours_display = format_hours_display(hours)
        
        # Format services
        services_summary = format_services_summary(booking)
        
        # Check discount
        discount_info = ""
        if len(hours) >= 3:
            discount_info = "\n🎉 <i>Знижка 10% вже застосована!</i>"
        
        # Photographer contact
        photographer_contact = ""
        if booking.photographer_choice == 'studio':
            photographer_contact = "\n\n💬 <b>Зв'язатись з фотографом:</b> @lonkilin"
        
        payment_message = f"""✅ <b>Підтверджено!</b>

{services_summary}{discount_info}

━━━━━━━━━━━━━━━━

💳 <b>Оберіть спосіб оплати:</b>

<b>Сума: {booking.total_price} грн</b>

━━━━━━━━━━━━━━━━

💡 <b>Онлайн-оплата:</b>
- Миттєве підтвердження
- Лише для фізичних осіб
- Картою будь-якого банку
- Google Pay / Apple Pay

📋 <b>Реквізити:</b>
- Тільки для фізичних осіб
- Підтвердження після скріншоту{photographer_contact}"""
        
        # Payment options
        keyboard = [
            [InlineKeyboardButton("💳 Оплата карткою (Google Pay, Apple Pay)", callback_data=f"pay_online_{booking_id}")],
            [InlineKeyboardButton("📋 Оплата на реквізити", callback_data=f"pay_manual_{booking_id}")],
            [InlineKeyboardButton("📄 Договір публічної оферти", url=f"{WEBSITE_URL}/static/contract.html")]
        ]
        
        await query.edit_message_text(
            payment_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    finally:
        db.close()


async def cancel_booking(query, context, first_booking_id):
    """Cancel booking"""
    db = get_db()
    
    try:
        # Get first booking
        first_booking = db.query(Booking).filter(Booking.id == first_booking_id).first()
        
        if not first_booking:
            await query.edit_message_text("❌ Бронювання не знайдено")
            return
        
        # Get all bookings in group
        group_id = first_booking.booking_group_id
        
        if group_id:
            bookings = db.query(Booking).filter(
                Booking.booking_group_id == group_id
            ).all()
        else:
            bookings = [first_booking]
        
        # Get client
        client = db.query(Client).filter(Client.id == first_booking.client_id).first()
        
        # Collect info before deletion
        hours = sorted([b.booking_hour for b in bookings])
        hours_display = format_hours_display(hours)
        date = first_booking.booking_date
        
        # Delete all bookings
        for booking in bookings:
            db.delete(booking)
        db.commit()
        
        # Update message
        try:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.edit_message_text(
                query.message.text + "\n\n❌ <b>СКАСОВАНО</b>",
                parse_mode='HTML'
            )
        except:
            pass
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"""❌ <b>Бронювання скасовано</b>

📅 {date.strftime('%d.%m.%Y')}
🕐 {hours_display}

Якщо передумаєте - створіть нове бронювання на сайті:
{WEBSITE_URL}""",
            reply_markup=get_main_keyboard(),
            parse_mode='HTML'
        )
        
        # Notify admins
        username = query.from_user.username
        tg = f"@{username}" if username else f"ID: {query.from_user.id}"
        
        await notify_admins(
            context,
            f"""❌ <b>Бронювання скасовано клієнтом</b>

ID: #{first_booking_id}
👤 {client.name}
📞 {client.phone}
💬 {tg}

📅 {date.strftime('%d.%m.%Y')}
🕐 {hours_display}"""
        )
        
    finally:
        db.close()

async def handle_text(update: Update, context):
    """Handle text messages (menu buttons)"""
    text = update.message.text.strip()
    
    # Menu buttons
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

async def handle_cancel_button(update: Update, context):
    """Handle cancel booking button"""
    user_id = update.effective_user.id
    db = get_db()
    
    try:
        # Find active bookings for this user
        bookings = db.query(Booking).filter(
            Booking.telegram_user_id == user_id,
            Booking.status.in_(['pending', 'confirmed'])
        ).all()
        
        if not bookings:
            await update.message.reply_text(
                "ℹ️ У вас немає активних бронювань для скасування.",
                reply_markup=get_main_keyboard()
            )
            return
        
        # Get first booking info
        first_booking = bookings[0]
        client = db.query(Client).filter(Client.id == first_booking.client_id).first()
        
        # Collect hours
        hours = sorted([b.booking_hour for b in bookings])
        hours_display = format_hours_display(hours)
        date = first_booking.booking_date
        
        # Delete all bookings
        for booking in bookings:
            db.delete(booking)
        db.commit()
        
        await update.message.reply_text(
            f"""❌ <b>Бронювання скасовано!</b>

📅 {date.strftime('%d.%m.%Y')}
🕐 {hours_display}

Якщо передумаєте - створіть нове бронювання на сайті.""",
            reply_markup=get_main_keyboard(),
            parse_mode='HTML'
        )
        
        # Clear context
        context.user_data.clear()
        
        # Notify admins
        username = update.effective_user.username
        tg = f"@{username}" if username else f"ID: {user_id}"
        
        await notify_admins(
            context,
            f"""❌ <b>Бронювання скасовано клієнтом</b>

ID: #{first_booking.id}
👤 {client.name}
📞 {client.phone}
💬 {tg}

📅 {date.strftime('%d.%m.%Y')}
🕐 {hours_display}"""
        )
        
    finally:
        db.close()

async def handle_photo(update: Update, context):
    """Handle payment screenshot"""
    user_id = update.effective_user.id
    db = get_db()
    
    try:
        # Find confirmed booking for this user
        bookings = db.query(Booking).filter(
            Booking.telegram_user_id == user_id,
            Booking.status == 'confirmed'
        ).all()
        
        if not bookings:
            await update.message.reply_text(
                "ℹ️ У вас немає підтверджених бронювань, які очікують оплату."
            )
            return
        
        # Update all bookings to paid
        for booking in bookings:
            booking.status = 'paid'
        db.commit()
        
        # Get first booking info
        first_booking = bookings[0]
        client = db.query(Client).filter(Client.id == first_booking.client_id).first()
        
        hours = sorted([b.booking_hour for b in bookings])
        hours_display = format_hours_display(hours)
        
        services_summary = format_services_summary(first_booking)
        
        discount_info = ""
        if len(hours) >= 3:
            discount_info = " (зі знижкою 10%)"
        
        # Confirm to client
        photographer_contact = ""
        if first_booking.photographer_choice == 'studio':
            photographer_contact = "\n\n💬 <b>Зв'язатись з фотографом для обговорення ідеї:</b> @lonkilin"
        
        await update.message.reply_text(
            f"""✅ <b>Квитанцію отримано!</b>

Оплата буде перевірена найближчим часом.

Дякуємо за бронювання{discount_info}! 🎉

Чекаємо на вас у студії! 📸

📅 {first_booking.booking_date.strftime('%d.%m.%Y')}
🕐 {hours_display}{photographer_contact}""",
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
        
        # Forward to admins
        username = update.effective_user.username
        tg = f"@{username}" if username else f"ID: {user_id}"
        
        admin_message = f"""💰 <b>Отримано оплату!</b>

ID: #{first_booking.id}
👤 {client.name}
📞 {client.phone}
💬 {tg}

📅 {first_booking.booking_date.strftime('%d.%m.%Y')}
🕐 {hours_display} ({len(hours)} год)

{services_summary}

📸 Скріншот квитанції:"""
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode='HTML'
                )
                await context.bot.forward_message(
                    chat_id=admin_id,
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.message_id
                )
            except:
                pass
        
        # NEW: Notify photographer if studio photographer selected
        if first_booking.photographer_choice == 'studio':
            photographer_message = f"""✅ <b>Оплата підтверджена!</b>

📸 <b>Ваша фотосесія:</b>

📅 Дата: {first_booking.booking_date.strftime('%d.%m.%Y')}
🕐 Час: {hours_display} ({len(hours)} год)

👤 Клієнт: {client.name}
📞 Телефон: {client.phone}

📋 <b>Деталі:</b>
{services_summary}

💰 Оплату отримано і перевірено{discount_info}

🎯 <b>Будьте готові!</b>
Клієнт чекає на вас у студії в призначений час."""
            
            try:
                await context.bot.send_message(
                    chat_id=PHOTOGRAPHER_ID,
                    text=photographer_message,
                    parse_mode='HTML'
                )
                # Also forward payment screenshot to photographer
                await context.bot.forward_message(
                    chat_id=PHOTOGRAPHER_ID,
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.message_id
                )
            except:
                pass
        
    finally:
        db.close()

# ========== MAIN ==========

def main():
    """Start bot"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("🤖 Bot started! (Simplified v2.0)")
    print("✅ All services selected on website")
    print("✅ Only confirmation and payment")
    print(f"👥 Admins: {len(ADMIN_IDS)}")
    if PHOTOGRAPHER_ID:
        print(f"📸 Photographer notifications: ENABLED (ID: {PHOTOGRAPHER_ID})")
    else:
        print("📸 Photographer notifications: DISABLED (set PHOTOGRAPHER_ID in .env)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
