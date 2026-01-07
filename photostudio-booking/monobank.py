import aiohttp
import os
from datetime import datetime, timedelta

MONOBANK_TOKEN = os.getenv('MONOBANK_TOKEN')
MONOBANK_API = 'https://api.monobank.ua/api/merchant'

class MonobankAPI:
    """Клас для роботи з Monobank API"""
    
    def __init__(self):
        self.token = MONOBANK_TOKEN
        self.headers = {
            'X-Token': self.token,
            'Content-Type': 'application/json'
        }
    
    async def create_invoice(self, amount: int, booking_id: int, client_name: str, description: str):
        """
        Створити рахунок для оплати
        
        Args:
            amount: Сума в копійках (1500 грн = 150000)
            booking_id: ID бронювання
            client_name: Ім'я клієнта
            description: Опис платежу
        
        Returns:
            dict: {
                'invoiceId': 'xxx',
                'pageUrl': 'https://...' - посилання для оплати
            }
        """
        
        # Сума в копійках
        amount_in_kopiykas = amount * 100
        
        # Webhook URL (куди Monobank надішле підтвердження)
        webhook_url = os.getenv('WEBSITE_URL') + '/api/monobank/webhook'
        
        payload = {
            'amount': amount_in_kopiykas,
            'ccy': 980,  # UAH
            'merchantPaymInfo': {
                'reference': str(booking_id),  # ID бронювання
                'destination': description,
                'comment': f'Бронювання #{booking_id} - {client_name}'
            },
            'redirectUrl': os.getenv('WEBSITE_URL'),  # Куди повернутись після оплати
            'webHookUrl': webhook_url,
            'validity': 86400,  # 24 години (в секундах)
            'paymentType': 'debit'  # Одразу списати гроші
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{MONOBANK_API}/invoice/create',
                headers=self.headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    error_text = await response.text()
                    raise Exception(f'Помилка створення рахунку: {error_text}')
    
    async def check_invoice_status(self, invoice_id: str):
        """
        Перевірити статус рахунку
        
        Args:
            invoice_id: ID рахунку від Monobank
        
        Returns:
            dict: Інформація про статус
        """
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{MONOBANK_API}/invoice/status',
                headers=self.headers,
                params={'invoiceId': invoice_id}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    error_text = await response.text()
                    raise Exception(f'Помилка перевірки статусу: {error_text}')
    
    @staticmethod
    def verify_signature(webhook_data: dict, public_key: str = None):
        """
        Перевірити підпис від Monobank (для безпеки)
        
        В продакшні обов'язково реалізувати!
        Зараз для простоти пропускаємо.
        """
        # TODO: Implement signature verification
        # https://api.monobank.ua/docs/acquiring.html#tag/Acquiring-API/Veb-huki
        return True

# Створити екземпляр
monobank = MonobankAPI()