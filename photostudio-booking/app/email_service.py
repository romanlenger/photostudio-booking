import os
from pathlib import Path
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

load_dotenv()

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
    MAIL_FROM=os.getenv("MAIL_FROM", "noreply@photostudio.com"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME", "Photo Studio Booking"),
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(__file__).parent / "templates"
)

async def send_verification_email(email: EmailStr, token: str, username: str):
    """Відправити email для верифікації"""
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8000")
    verification_url = f"{frontend_url}/verify-email?token={token}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .content {{
                background: white;
                padding: 40px;
                border-radius: 10px;
            }}
            h1 {{
                color: #667eea;
            }}
            .button {{
                display: inline-block;
                padding: 15px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                color: white;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="content">
                <h1>📸 Вітаємо в Фотостудії!</h1>
                <p>Привіт, {username}!</p>
                <p>Дякуємо за реєстрацію. Будь ласка, підтвердіть свою електронну адресу, натиснувши кнопку нижче:</p>
                <a href="{verification_url}" class="button">Підтвердити Email</a>
                <p>Або скопіюйте посилання:</p>
                <p style="word-break: break-all; color: #667eea;">{verification_url}</p>
                <p>Це посилання дійсне протягом 24 годин.</p>
                <p>Якщо ви не реєструвалися на нашому сайті, просто ігноруйте цей лист.</p>
            </div>
            <div class="footer">
                <p>© 2025 Photo Studio. Всі права захищені.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Підтвердження реєстрації - Photo Studio",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html
    )
    
    fm = FastMail(conf)
    await fm.send_message(message)

async def send_password_reset_email(email: EmailStr, token: str, username: str):
    """Відправити email для скидання пароля"""
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8000")
    reset_url = f"{frontend_url}/reset-password?token={token}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .content {{
                background: white;
                padding: 40px;
                border-radius: 10px;
            }}
            h1 {{
                color: #667eea;
            }}
            .button {{
                display: inline-block;
                padding: 15px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .warning {{
                background: #fff3cd;
                padding: 15px;
                border-left: 4px solid #ffc107;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                color: white;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="content">
                <h1>🔐 Скидання пароля</h1>
                <p>Привіт, {username}!</p>
                <p>Ми отримали запит на скидання пароля для вашого акаунту.</p>
                <p>Натисніть кнопку нижче, щоб встановити новий пароль:</p>
                <a href="{reset_url}" class="button">Скинути пароль</a>
                <p>Або скопіюйте посилання:</p>
                <p style="word-break: break-all; color: #667eea;">{reset_url}</p>
                <div class="warning">
                    <strong>⚠️ Важливо:</strong> Це посилання дійсне лише протягом 1 години.
                </div>
                <p>Якщо ви не запитували скидання пароля, просто проігноруйте цей лист. Ваш пароль залишиться без змін.</p>
            </div>
            <div class="footer">
                <p>© 2025 Photo Studio. Всі права захищені.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Скидання пароля - Photo Studio",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html
    )
    
    fm = FastMail(conf)
    await fm.send_message(message)

async def send_booking_confirmation_email(email: EmailStr, booking_details: dict):
    """Відправити підтвердження бронювання"""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .content {{
                background: white;
                padding: 40px;
                border-radius: 10px;
            }}
            h1 {{
                color: #667eea;
            }}
            .booking-info {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #e0e0e0;
            }}
            .info-label {{
                font-weight: bold;
                color: #667eea;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                color: white;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="content">
                <h1>✅ Бронювання підтверджено!</h1>
                <p>Привіт, {booking_details['name']}!</p>
                <p>Ваше бронювання успішно підтверджено.</p>
                
                <div class="booking-info">
                    <h3>Деталі бронювання:</h3>
                    <div class="info-row">
                        <span class="info-label">Дата:</span>
                        <span>{booking_details['date']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Час:</span>
                        <span>{booking_details['time']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Телефон:</span>
                        <span>{booking_details['phone']}</span>
                    </div>
                </div>
                
                <p>Очікуємо на вас! У разі потреби змін, зв'яжіться з нами.</p>
            </div>
            <div class="footer">
                <p>© 2025 Photo Studio. Всі права захищені.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Підтвердження бронювання - Photo Studio",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html
    )
    
    fm = FastMail(conf)
    await fm.send_message(message)
