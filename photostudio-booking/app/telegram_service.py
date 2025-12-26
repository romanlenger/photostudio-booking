"""
Telegram Bot Service для CLIQUE Photostudio
Відправляє сповіщення про нові бронювання
"""
import os
import logging
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError
from datetime import datetime

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Клас для відправки Telegram сповіщень"""
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.admin_chat_ids = self._parse_chat_ids()
        self.bot = None
        
        if self.bot_token:
            try:
                self.bot = Bot(token=self.bot_token)
                logger.info("✅ Telegram Bot ініціалізовано")
            except Exception as e:
                logger.error(f"❌ Помилка ініціалізації Telegram Bot: {e}")
        else:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN не встановлено")
    
    def _parse_chat_ids(self) -> list:
        """Парсити chat_id з змінної оточення"""
        chat_ids_str = os.getenv("TELEGRAM_ADMIN_CHAT_IDS", "")
        if not chat_ids_str:
            return []
        
        # Підтримка декількох chat_id через кому
        return [int(id.strip()) for id in chat_ids_str.split(",") if id.strip()]
    
    async def send_new_booking_notification(
        self,
        client_name: str,
        client_phone: str,
        booking_date: str,
        booking_hour: int,
        booking_id: int
    ) -> bool:
        """Відправити сповіщення про нове бронювання"""
        
        if not self.bot or not self.admin_chat_ids:
            logger.warning("Telegram бот не налаштований або немає адмінів для сповіщень")
            return False
        
        # Форматування дати
        try:
            date_obj = datetime.strptime(booking_date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %B %Y")
            month_names = {
                "January": "січня", "February": "лютого", "March": "березня",
                "April": "квітня", "May": "травня", "June": "червня",
                "July": "липня", "August": "серпня", "September": "вересня",
                "October": "жовтня", "November": "листопада", "December": "грудня"
            }
            for eng, ukr in month_names.items():
                formatted_date = formatted_date.replace(eng, ukr)
        except:
            formatted_date = booking_date
        
        # Форматування часу
        time_range = f"{booking_hour:02d}:00 - {booking_hour+1:02d}:00"
        
        # Повідомлення
        message = f"""
🎉 <b>Нове бронювання!</b>

📅 <b>Дата:</b> {formatted_date}
🕐 <b>Час:</b> {time_range}

👤 <b>Клієнт:</b> {client_name}
📞 <b>Телефон:</b> <code>{client_phone}</code>

🆔 Бронювання #{booking_id}

💼 <b>CLIQUE Photostudio</b>
"""
        
        success_count = 0
        
        # Відправити всім адмінам
        for chat_id in self.admin_chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="HTML"
                )
                success_count += 1
                logger.info(f"✅ Повідомлення відправлено адміну {chat_id}")
            except TelegramError as e:
                logger.error(f"❌ Помилка відправки адміну {chat_id}: {e}")
        
        return success_count > 0
    
    async def send_booking_cancelled_notification(
        self,
        client_name: str,
        booking_date: str,
        booking_hour: int,
        booking_id: int
    ) -> bool:
        """Відправити сповіщення про скасування бронювання"""
        
        if not self.bot or not self.admin_chat_ids:
            return False
        
        # Форматування дати
        try:
            date_obj = datetime.strptime(booking_date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %B %Y")
            month_names = {
                "January": "січня", "February": "лютого", "March": "березня",
                "April": "квітня", "May": "травня", "June": "червня",
                "July": "липня", "August": "серпня", "September": "вересня",
                "October": "жовтня", "November": "листопада", "December": "грудня"
            }
            for eng, ukr in month_names.items():
                formatted_date = formatted_date.replace(eng, ukr)
        except:
            formatted_date = booking_date
        
        time_range = f"{booking_hour:02d}:00 - {booking_hour+1:02d}:00"
        
        message = f"""
❌ <b>Бронювання скасовано</b>

📅 <b>Дата:</b> {formatted_date}
🕐 <b>Час:</b> {time_range}

👤 <b>Клієнт:</b> {client_name}

🆔 Бронювання #{booking_id}

💼 <b>CLIQUE Photostudio</b>
"""
        
        success_count = 0
        
        for chat_id in self.admin_chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="HTML"
                )
                success_count += 1
                logger.info(f"✅ Сповіщення про скасування відправлено адміну {chat_id}")
            except TelegramError as e:
                logger.error(f"❌ Помилка відправки адміну {chat_id}: {e}")
        
        return success_count > 0
    
    async def send_test_message(self, chat_id: int) -> bool:
        """Відправити тестове повідомлення"""
        
        if not self.bot:
            return False
        
        message = """
✅ <b>Тестове повідомлення</b>

Якщо ви бачите це повідомлення, значить Telegram бот налаштовано правильно!

💼 <b>CLIQUE Photostudio</b>
"""
        
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="HTML"
            )
            logger.info(f"✅ Тестове повідомлення відправлено в чат {chat_id}")
            return True
        except TelegramError as e:
            logger.error(f"❌ Помилка відправки тестового повідомлення: {e}")
            return False

# Глобальний екземпляр
telegram_notifier = TelegramNotifier()
