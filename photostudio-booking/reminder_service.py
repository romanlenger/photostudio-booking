import os
import asyncio
from datetime import datetime, timedelta
from telegram import Bot
import logging
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal
from app.models import Booking, Client

sent_reminders_cache = {}

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфігурація
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    try:
        with open("bot_token.txt", "r") as f:
            BOT_TOKEN = f.read().strip()
    except:
        raise ValueError("BOT_TOKEN not found!")

CHECK_INTERVAL = 1 * 60  # Перевірка кожні 15 хвилин
REMINDER_24H = 24 * 60  # 24 години в хвилинах
REMINDER_3H = 1 * 60    # 3 години в хвилинах
TOLERANCE = 2       # Толерантність ±15 хвилин

def format_hours_display(hours):
    """Форматувати години для відображення"""
    if not hours:
        return ""
    if len(hours) == 1:
        return f"{hours[0]}:00"
    
    is_consecutive = all(hours[i] == hours[i-1] + 1 for i in range(1, len(hours)))
    
    if is_consecutive:
        return f"{hours[0]}:00-{hours[-1] + 1}:00"
    else:
        return ", ".join(f"{h}:00" for h in hours)

def get_bookings_needing_reminder(db, reminder_minutes):
    """
    Отримати бронювання які потребують нагадування
    reminder_minutes: 1440 для 24 години, 180 для 3 години
    """
    now = datetime.now() + timedelta(hours=2)  # Локальний час Києва без часової зони
    target_time = now + timedelta(minutes=reminder_minutes)
    
    # Часові рамки з толерантністю
    time_min = target_time - timedelta(minutes=TOLERANCE)
    time_max = target_time + timedelta(minutes=TOLERANCE)
    
    logger.debug(f"Checking for {reminder_minutes/60}h reminders between {time_min} and {time_max}")
    
    # Знайти всі paid/confirmed бронювання з telegram_user_id
    bookings = db.query(Booking).filter(
        Booking.status.in_(['paid', 'confirmed']),
        Booking.telegram_user_id.isnot(None),
        Booking.booking_date == target_time.date()
    ).all()
    
    results = []
    processed_groups = set()  # Щоб не обробляти одну групу двічі
    
    for booking in bookings:
        # Час початку бронювання
        booking_datetime = datetime.combine(
            booking.booking_date,
            datetime.min.time().replace(hour=booking.booking_hour)
        )
        
        # Перевірка чи потрапляє в часові рамки
        if time_min <= booking_datetime <= time_max:
            # Якщо це група, додати тільки один раз
            if booking.booking_group_id:
                if booking.booking_group_id not in processed_groups:
                    results.append(booking)
                    processed_groups.add(booking.booking_group_id)
            else:
                results.append(booking)
    
    return results

async def send_reminder(bot, booking, hours_before):
    """Відправити нагадування клієнту"""
    cache_key = f"{booking.id}_{hours_before}h"
    
    # Перевірка чи вже відправляли
    if cache_key in sent_reminders_cache:
        logger.info(f"⏭️  Already sent {hours_before}h reminder for booking {booking.id}")
        return False
    
    try:
        db = SessionLocal()
        
        # Отримати клієнта
        client = db.query(Client).filter(Client.id == booking.client_id).first()
        if not client:
            logger.error(f"Client not found for booking {booking.id}")
            return False
        
        # Отримати всі години в групі
        if booking.booking_group_id:
            bookings = db.query(Booking).filter(
                Booking.booking_group_id == booking.booking_group_id
            ).all()
        else:
            bookings = [booking]
        
        hours = sorted([b.booking_hour for b in bookings])
        hours_display = format_hours_display(hours)
        
        # Перевірка чи є знижка
        has_discount = len(hours) >= 3
        discount_text = "\n🎉 <b>Застосовано знижку 10%!</b>" if has_discount else ""
        
        # Emoji для часу
        time_emoji = "⏰" if hours_before == 24 else "🔔"
        time_text = "24 години" if hours_before == 24 else "60 хвилин"  # ← Виправив на "3 години"
        
        # Формування повідомлення
        message = f"""{time_emoji} <b>Нагадування!</b>

До вашого бронювання залишилось {time_text}!

📅 <b>Дата:</b> {booking.booking_date.strftime('%d.%m.%Y')}
🕐 <b>Час:</b> {hours_display} ({len(hours)} год)

💰 <b>Вартість:</b> {booking.total_price} грн{discount_text}

📍 <b>Адреса студії:</b>
м. Бровари, Київська область
провулок Івана Сокура, 1

📞 <b>Контакт:</b> @clique_admin

{"⏰ Не забудьте прийти вчасно!" if hours_before == 24 else "🎯 Скоро зустрічаємось! Чекаємо на вас!"}"""
        
        # Відправка повідомлення
        await bot.send_message(
            chat_id=booking.telegram_user_id,
            text=message,
            parse_mode='HTML'
        )
        
        # Додати в кеш і залогувати
        sent_reminders_cache[cache_key] = datetime.now()
        logger.info(f"✅ Sent {hours_before}h reminder for booking {booking.id} to user {booking.telegram_user_id}")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send reminder for booking {booking.id}: {e}")
        return False

async def check_and_send_reminders():
    """Основна функція перевірки та відправки нагадувань"""
    logger.info("🔍 Checking for bookings needing reminders...")
    
    bot = Bot(token=BOT_TOKEN)
    db = SessionLocal()
    
    try:
        # Перевірка для 24 годин
        bookings_24h = get_bookings_needing_reminder(db, REMINDER_24H)
        logger.info(f"📋 Found {len(bookings_24h)} bookings needing 24h reminder")
        
        for booking in bookings_24h:
            await send_reminder(bot, booking, 24)
            await asyncio.sleep(1)  # Невелика затримка між повідомленнями
        
        # Перевірка для 3 годин
        bookings_3h = get_bookings_needing_reminder(db, REMINDER_3H)
        logger.info(f"📋 Found {len(bookings_3h)} bookings needing 3h reminder")
        
        for booking in bookings_3h:
            await send_reminder(bot, booking, 3)
            await asyncio.sleep(1)
        
        logger.info(f"✅ Reminder check completed. Sent: {len(bookings_24h)} × 24h, {len(bookings_3h)} × 3h")
        
    except Exception as e:
        logger.error(f"❌ Error during reminder check: {e}")
    finally:
        db.close()

async def main_loop():
    """Головний цикл перевірки"""
    logger.info("🚀 Booking Reminders Service started")
    logger.info(f"⏱️  Check interval: {CHECK_INTERVAL/60} minutes")
    logger.info(f"📅 Reminders: 24 hours and 3 hours before booking")
    
    while True:
        try:
            await check_and_send_reminders()
        except Exception as e:
            logger.error(f"❌ Error in main loop: {e}")
        
        # Чекати до наступної перевірки
        logger.info(f"💤 Sleeping for {CHECK_INTERVAL/60} minutes...")
        await asyncio.sleep(CHECK_INTERVAL)

def main():
    """Запуск сервісу"""
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("⛔ Service stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()