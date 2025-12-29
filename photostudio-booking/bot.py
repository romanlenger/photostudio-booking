"""
Telegram bot for photostudio booking confirmation
Uses python-telegram-bot library (same as telegram_service)
"""
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from sqlalchemy.orm import Session
from datetime import datetime

# Database imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal
from app.models import Booking, Client


# Bot setup
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    try:
        with open("bot_token.txt", "r") as f:
            BOT_TOKEN = f.read().strip()
    except:
        raise ValueError("BOT_TOKEN not found!")

# Admin IDs
ADMIN_IDS_STR = os.getenv("TELEGRAM_ADMIN_CHAT_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]

# Studio rules
STUDIO_RULES = os.getenv("STUDIO_RULES")

# Payment details
PAYMENT_DETAILS = """💳 Реквізити для оплати:

Картка ПриватБанк: 5168 7574 1234 5678
Отримувач: Кріпак Юлія Павлівна
Сума: (тут бот має порахувати сам сумму, це для тебе CLaude) грн

📸 Після оплати надішліть скріншот квитанції в цей чат.
"""



def get_db():
    """Get database session"""
    db = SessionLocal()
    return db


async def notify_admins(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Send notification to all admins"""
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message, parse_mode='HTML')
        except Exception as e:
            print(f"Failed to notify admin {admin_id}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            "👋 Вітаю, адміне!\n\n"
            "Ви будете отримувати сповіщення про всі бронювання.\n\n"
            "Команди:\n"
            "/start - це повідомлення\n"
            "/help - довідка"
        )
        return
    
    # Check if this is booking confirmation
    if context.args and context.args[0].startswith("booking_"):
        booking_id = context.args[0].replace("booking_", "")
        await handle_booking_confirmation(update, context, booking_id)
    else:
        await update.message.reply_text(
            "👋 Вітаємо в фотостудії CLIQUE!\n\n"
            "Для бронювання перейдіть на наш сайт:\n"
            "🌐 http://192.168.88.26:8000"
        )


async def handle_booking_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, booking_id: str):
    """Handle booking confirmation flow"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "без username"
    
    db = get_db()
    
    try:
        # Get booking from database
        booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
        
        if not booking:
            await update.message.reply_text(
                "❌ Бронювання не знайдено.\n\n"
                "Можливо воно вже було скасоване або видалене."
            )
            return
        
        # Get client
        client = db.query(Client).filter(Client.id == booking.client_id).first()
        
        # Check if already confirmed
        if booking.status in ['confirmed', 'paid']:
            await update.message.reply_text(
                f"✅ Це бронювання вже підтверджено!\n\n"
                f"📅 Дата: {booking.booking_date}\n"
                f"🕐 Час: {booking.booking_hour}:00\n"
                f"👤 Ім'я: {client.name}"
            )
            return
        
        # Update telegram_user_id
        booking.telegram_user_id = user_id
        db.commit()
        
        # Send rules + confirmation buttons
        text = f"""{STUDIO_RULES}

━━━━━━━━━━━━━━━━━━

📅 <b>Ваше бронювання:</b>

Дата: {booking.booking_date.strftime('%d.%m.%Y')}
Час: {booking.booking_hour}:00
Ім'я: {client.name}
Телефон: {client.phone}

━━━━━━━━━━━━━━━━━━

❓ Підтверджуєте бронювання?
"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Підтвердити", callback_data=f"confirm_{booking_id}"),
                InlineKeyboardButton("❌ Скасувати", callback_data=f"cancel_{booking_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        sent = await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        
        # Save message_id
        booking.confirmation_message_id = sent.message_id
        db.commit()
        
        # Notify admins
        telegram_info = f"@{username}" if username != "без username" else f"ID: {user_id}"
        
        await notify_admins(
            context,
            f"📬 <b>Нове бронювання очікує підтвердження</b>\n\n"
            f"ID бронювання: #{booking_id}\n"
            f"👤 {client.name}\n"
            f"📞 {client.phone}\n"
            f"💬 Telegram: {telegram_info}\n"
            f"📅 {booking.booking_date} о {booking.booking_hour}:00"
        )
    
    finally:
        db.close()


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    try:
        action, booking_id = query.data.split("_", 1)
        
        if action == "confirm":
            await confirm_booking(update, context, booking_id)
        elif action == "cancel":
            await cancel_booking(update, context, booking_id)
        elif action == "pay":
            await handle_online_payment(update, context, booking_id)
    except Exception as e:
        await query.answer(f"Помилка: {str(e)}", show_alert=True)


async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE, booking_id: str):
    """Confirm booking and send payment details"""
    query = update.callback_query
    db = get_db()
    
    try:
        booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
        
        if not booking:
            await query.answer("❌ Бронювання не знайдено", show_alert=True)
            return
        
        client = db.query(Client).filter(Client.id == booking.client_id).first()
        
        # Update status to confirmed
        booking.status = "confirmed"
        db.commit()
        
        # Edit original message
        try:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.edit_message_text(
                query.message.text + "\n\n✅ <b>ПІДТВЕРДЖЕНО</b>",
                parse_mode='HTML'
            )
        except:
            pass
        
        # Send payment details
        payment_text = PAYMENT_DETAILS.format(
            date=booking.booking_date,
            time=booking.booking_hour
        )
        
        keyboard = [[InlineKeyboardButton("💰 Оплатити онлайн", callback_data=f"pay_{booking_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=payment_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        await query.answer("✅ Бронювання підтверджено!")
        
        # Get telegram username
        username = query.from_user.username
        telegram_info = f"@{username}" if username else f"ID: {query.from_user.id}"
        
        # Notify admins
        await notify_admins(
            context,
            f"✅ <b>Бронювання підтверджено</b>\n\n"
            f"ID бронювання: #{booking_id}\n"
            f"👤 {client.name}\n"
            f"📞 {client.phone}\n"
            f"💬 Telegram: {telegram_info}\n"
            f"📅 {booking.booking_date} о {booking.booking_hour}:00\n\n"
            f"⏳ Очікуємо оплату..."
        )
    
    finally:
        db.close()


async def cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE, booking_id: str):
    """Cancel and delete booking"""
    query = update.callback_query
    db = get_db()
    
    try:
        booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
        
        if not booking:
            await query.answer("❌ Бронювання не знайдено", show_alert=True)
            return
        
        client = db.query(Client).filter(Client.id == booking.client_id).first()
        
        # Save info for notification
        client_name = client.name
        client_phone = client.phone
        booking_date = booking.booking_date
        booking_hour = booking.booking_hour
        
        # Get telegram username
        username = query.from_user.username
        telegram_info = f"@{username}" if username else f"ID: {query.from_user.id}"
        
        # Delete from database
        db.delete(booking)
        db.commit()
        
        # Edit message
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
            text="❌ Бронювання скасовано.\n\n"
                 "Якщо передумаєте - створіть нове бронювання на сайті."
        )
        
        await query.answer("Бронювання скасовано")
        
        # Notify admins
        await notify_admins(
            context,
            f"❌ <b>Бронювання скасовано клієнтом</b>\n\n"
            f"ID бронювання: #{booking_id}\n"
            f"👤 {client_name}\n"
            f"📞 {client_phone}\n"
            f"💬 Telegram: {telegram_info}\n"
            f"📅 {booking_date} о {booking_hour}:00"
        )
    
    finally:
        db.close()


async def handle_online_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, booking_id: str):
    """Handle online payment (placeholder)"""
    query = update.callback_query
    
    await query.answer("💳 Онлайн оплата буде додана незабаром!", show_alert=True)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="💳 <b>Онлайн оплата</b>\n\n"
             "Функція знаходиться в розробці.\n"
             "Поки що використовуйте оплату за реквізитами вище.\n\n"
             "Після оплати надішліть скріншот квитанції.",
        parse_mode='HTML'
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment receipt photo"""
    user_id = update.effective_user.id
    db = get_db()
    
    try:
        # Find user's booking
        booking = db.query(Booking).filter(
            Booking.telegram_user_id == user_id,
            Booking.status == 'confirmed'
        ).first()
        
        if booking:
            client = db.query(Client).filter(Client.id == booking.client_id).first()
            
            # Update status to paid
            booking.status = "paid"
            db.commit()
            
            await update.message.reply_text(
                "✅ Дякуємо! Квитанцію отримано.\n\n"
                "Оплата буде перевірена найближчим часом.\n"
                "Ми зв'яжемось з вами для підтвердження."
            )
            
            # Forward to admins
            username = update.effective_user.username
            telegram_info = f"@{username}" if username else f"ID: {user_id}"
            
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.forward_message(
                        chat_id=admin_id,
                        from_chat_id=update.message.chat_id,
                        message_id=update.message.message_id
                    )
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"💰 <b>Отримано квитанцію про оплату</b>\n\n"
                             f"ID бронювання: #{booking.id}\n"
                             f"👤 {client.name}\n"
                             f"📞 {client.phone}\n"
                             f"💬 Telegram: {telegram_info}\n"
                             f"📅 {booking.booking_date} о {booking.booking_hour}:00\n\n"
                             f"❗️ Перевірте оплату!",
                        parse_mode='HTML'
                    )
                except:
                    pass
        else:
            await update.message.reply_text(
                "ℹ️ Спочатку створіть бронювання на сайті."
            )
    
    finally:
        db.close()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await update.message.reply_text(
        "ℹ️ <b>Довідка</b>\n\n"
        "Цей бот допомагає підтвердити бронювання фотостудії.\n\n"
        "<b>Як працює:</b>\n"
        "1. Створіть бронювання на сайті\n"
        "2. Перейдіть в цей бот\n"
        "3. Підтвердіть бронювання\n"
        "4. Оплатіть за реквізитами\n"
        "5. Надішліть квитанцію\n\n"
        "🌐 Сайт: http://192.168.88.26:8000",
        parse_mode='HTML'
    )


def main():
    """Run the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Run bot
    print("🤖 Bot started!")
    print(f"👥 Admin IDs: {ADMIN_IDS}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
