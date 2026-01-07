from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from datetime import date, timedelta, datetime
import calendar
import os
import uuid
import logging

from . import models, schemas
from .database import engine, get_db
from .auth import verify_password, create_access_token, get_current_admin
from .telegram_service import telegram_notifier

# Створення таблиць
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Photo Studio Booking System", version="2.0.0")

# Статичні файли
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Головна сторінка з календарем (для користувачів)"""
    return FileResponse("static/index.html")

@app.get("/admin")
@app.get("/admin/")
async def admin_page():
    """Сторінка адміністратора"""
    return FileResponse("static/admin.html")

# Admin Authentication
@app.post("/api/admin/login", response_model=schemas.LoginResponse)
def admin_login(login_data: schemas.LoginRequest):
    """Авторизація адміна"""
    if not verify_password(login_data.password):
        raise HTTPException(
            status_code=401,
            detail="Неправильний пароль"
        )
    
    access_token = create_access_token(data={"role": "admin"})
    return schemas.LoginResponse(access_token=access_token)

@app.post("/api/bookings/", response_model=schemas.BookingGroupResponse, status_code=201)
async def create_booking(
    booking: schemas.BookingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Створити нове бронювання з МНОЖИННИМИ ГОДИНАМИ
    
    Клієнт може обрати декілька годин (наприклад [14, 15, 16])
    Система створить окремий запис для кожної години
    Всі записи будуть зв'язані через booking_group_id
    """
    
    # Перевірити, чи всі обрані години доступні
    for hour in booking.booking_hours:
        existing_booking = db.query(models.Booking).filter(
            models.Booking.booking_date == booking.booking_date,
            models.Booking.booking_hour == hour,
            models.Booking.status.in_(['pending', 'confirmed', 'paid'])
        ).first()
        
        if existing_booking:
            raise HTTPException(
                status_code=400, 
                detail=f"Година {hour}:00 вже зайнята. Оберіть іншу годину."
            )
    
    try:
        # Знайти або створити клієнта
        client = db.query(models.Client).filter(
            models.Client.phone == booking.phone
        ).first()
        
        if not client:
            client = models.Client(name=booking.name, phone=booking.phone)
            db.add(client)
            db.flush()
        
        # Згенерувати booking_group_id для зв'язку всіх годин
        booking_group_id = str(uuid.uuid4())
        
        # Створити ОКРЕМИЙ запис для КОЖНОЇ години
        booking_ids = []
        
        for hour in booking.booking_hours:
            db_booking = models.Booking(
                client_id=client.id,
                booking_date=booking.booking_date,
                booking_hour=hour,
                booking_group_id=booking_group_id,
                status="pending",
                # Всі послуги однакові для всіх годин
                people_count=booking.people_count,
                zone_choice=booking.zone_choice,
                animals_count=booking.animals_count,
                background_choice=booking.background_choice,
                photographer_choice=booking.photographer_choice,
                total_price=booking.total_price
            )
            db.add(db_booking)
            db.flush()
            booking_ids.append(db_booking.id)
        
        db.commit()
        
        # Створити Telegram deep link (використовуємо ID першого бронювання)
        first_booking_id = booking_ids[0]
        bot_username = os.getenv("BOT_USERNAME", "your_bot_username")
        telegram_link = f"https://t.me/{bot_username}?start=booking_{first_booking_id}"
        
        # Відправити сповіщення адміну (в фоновому режимі)
        hours_display = format_hours_display(booking.booking_hours)
        background_tasks.add_task(
            telegram_notifier.send_new_booking_notification,
            client_name=booking.name,
            client_phone=booking.phone,
            booking_date=str(booking.booking_date),
            booking_hours=hours_display,
            booking_id=first_booking_id,
            people_count=booking.people_count,
            zone_choice=booking.zone_choice,
            animals_count=booking.animals_count,
            background_choice=booking.background_choice,
            photographer_choice=booking.photographer_choice,
            total_price=booking.total_price
        )
        
        # Повернути відповідь
        return schemas.BookingGroupResponse(
            booking_group_id=booking_group_id,
            booking_ids=booking_ids,
            hours=booking.booking_hours,
            client_name=booking.name,
            client_phone=booking.phone,
            booking_date=booking.booking_date,
            status="pending",
            people_count=booking.people_count,
            zone_choice=booking.zone_choice,
            animals_count=booking.animals_count,
            background_choice=booking.background_choice,
            photographer_choice=booking.photographer_choice,
            total_price=booking.total_price,
            telegram_link=telegram_link
        )
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Одна з обраних годин щойно була заброньована. Спробуйте ще раз."
        )

def format_hours_display(hours: List[int]) -> str:
    """
    Форматувати години для відображення
    [14, 15, 16] → "14:00-17:00"
    [14, 17] → "14:00, 17:00"
    """
    if not hours:
        return ""
    if len(hours) == 1:
        return f"{hours[0]}:00"
    
    # Перевірити чи години підряд
    is_consecutive = all(hours[i] == hours[i-1] + 1 for i in range(1, len(hours)))
    
    if is_consecutive:
        # Показати як діапазон
        return f"{hours[0]}:00-{hours[-1] + 1}:00"
    else:
        # Показати окремо
        return ", ".join(f"{h}:00" for h in hours)

@app.get("/api/bookings/", response_model=List[schemas.BookingResponse])
def get_bookings(
    start_date: date = Query(None),
    end_date: date = Query(None),
    db: Session = Depends(get_db)
):
    """Отримати всі бронювання з фільтрацією по датах"""
    query = db.query(models.Booking)
    
    if start_date:
        query = query.filter(models.Booking.booking_date >= start_date)
    if end_date:
        query = query.filter(models.Booking.booking_date <= end_date)
    
    bookings = query.order_by(
        models.Booking.booking_date,
        models.Booking.booking_hour
    ).all()
    
    return bookings

@app.get("/api/calendar/{year}/{month}", response_model=List[schemas.DayStatusResponse])
def get_month_calendar(
    year: int,
    month: int,
    db: Session = Depends(get_db)
):
    """Отримати статус всіх днів місяця"""
    
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Місяць повинен бути від 1 до 12")
    
    # Отримати всі дні місяця
    _, num_days = calendar.monthrange(year, month)
    first_day = date(year, month, 1)
    last_day = date(year, month, num_days)
    
    # Отримати всі АКТИВНІ бронювання за місяць
    bookings = db.query(models.Booking).filter(
        models.Booking.booking_date >= first_day,
        models.Booking.booking_date <= last_day,
        models.Booking.status.in_(['pending', 'confirmed', 'paid'])
    ).all()
    
    # Групувати бронювання по датах
    bookings_by_date = {}
    for booking in bookings:
        if booking.booking_date not in bookings_by_date:
            bookings_by_date[booking.booking_date] = []
        bookings_by_date[booking.booking_date].append(booking.booking_hour)
    
    # Робочі години студії
    WORK_HOURS = list(range(9, 22))  # 9-21
    
    # Створити відповідь для кожного дня
    result = []
    for day in range(1, num_days + 1):
        current_date = date(year, month, day)
        booked_hours = bookings_by_date.get(current_date, [])
        available_hours = [h for h in WORK_HOURS if h not in booked_hours]
        
        result.append(schemas.DayStatusResponse(
            date=current_date,
            has_bookings=len(booked_hours) > 0,
            available_hours=available_hours,
            booked_hours=booked_hours
        ))
    
    return result

@app.get("/api/day/{booking_date}", response_model=schemas.DayStatusResponse)
def get_day_status(
    booking_date: date,
    db: Session = Depends(get_db)
):
    """Отримати статус конкретного дня"""
    
    bookings = db.query(models.Booking).filter(
        models.Booking.booking_date == booking_date,
        models.Booking.status.in_(['pending', 'confirmed', 'paid'])
    ).all()
    
    WORK_HOURS = list(range(9, 22))
    booked_hours = [b.booking_hour for b in bookings]
    available_hours = [h for h in WORK_HOURS if h not in booked_hours]
    
    return schemas.DayStatusResponse(
        date=booking_date,
        has_bookings=len(bookings) > 0,
        available_hours=available_hours,
        booked_hours=booked_hours
    )

# ADMIN ENDPOINTS

@app.get("/api/admin/bookings/list")
def get_admin_bookings_list(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """Отримати список всіх бронювань за період (для адміна)"""
    
    bookings = db.query(models.Booking).filter(
        models.Booking.booking_date >= start_date,
        models.Booking.booking_date <= end_date,
        models.Booking.status.in_(['pending', 'confirmed', 'paid'])
    ).order_by(models.Booking.booking_date, models.Booking.booking_hour).all()
    
    # Форматувати результат
    result = []
    for booking in bookings:
        # Підрахувати години в групі
        hours_in_group = 1
        if booking.booking_group_id:
            hours_in_group = db.query(models.Booking).filter(
                models.Booking.booking_group_id == booking.booking_group_id,
                models.Booking.status.in_(['pending', 'confirmed', 'paid'])
            ).count()
        
        has_discount = hours_in_group >= 3
        
        result.append({
            'id': booking.id,
            'booking_date': booking.booking_date,
            'booking_hour': booking.booking_hour,
            'booking_group_id': booking.booking_group_id,
            'status': booking.status,
            'client': {
                'id': booking.client.id,
                'name': booking.client.name,
                'phone': booking.client.phone
            },
            'people_count': booking.people_count,
            'zone_choice': booking.zone_choice,
            'animals_count': booking.animals_count,
            'background_choice': booking.background_choice,
            'photographer_choice': booking.photographer_choice,
            'total_price': booking.total_price,
            'hours_in_group': hours_in_group,
            'has_discount': has_discount,
            'created_at': booking.created_at
        })
    
    return result

@app.get("/api/admin/day/{booking_date}", response_model=schemas.AdminDayStatusResponse)
@app.get("/api/admin/bookings/{booking_date}", response_model=schemas.AdminDayStatusResponse)
def get_admin_day_status(
    booking_date: date,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """Отримати детальну інформацію про всі бронювання в конкретний день (для адміна)"""
    
    # Отримати всі бронювання на цю дату (включаючи скасовані)
    bookings = db.query(models.Booking).filter(
        models.Booking.booking_date == booking_date
    ).all()
    
    # Підрахувати кількість годин в кожній групі
    group_hours_count = {}
    for booking in bookings:
        if booking.status in ['pending', 'confirmed', 'paid'] and booking.booking_group_id:
            if booking.booking_group_id not in group_hours_count:
                group_hours_count[booking.booking_group_id] = 0
            group_hours_count[booking.booking_group_id] += 1
    
    # Створити словник з інформацією про бронювання
    booking_info = {}
    for booking in bookings:
        if booking.status in ['pending', 'confirmed', 'paid']:
            client = booking.client
            hours_in_group = group_hours_count.get(booking.booking_group_id, 1) if booking.booking_group_id else 1
            has_discount = hours_in_group >= 3
            
            booking_info[booking.booking_hour] = {
                'client_name': client.name,
                'client_phone': client.phone,
                'booking_id': booking.id,
                'booking_group_id': booking.booking_group_id,
                'photographer_choice': booking.photographer_choice,
                'total_price': booking.total_price,
                'hours_in_group': hours_in_group,
                'has_discount': has_discount
            }
    
    # Створити список для всіх робочих годин
    WORK_HOURS = list(range(9, 22))
    result_bookings = []
    
    for hour in WORK_HOURS:
        if hour in booking_info:
            info = booking_info[hour]
            result_bookings.append(schemas.BookingDetailResponse(
                hour=hour,
                is_booked=True,
                client_name=info['client_name'],
                client_phone=info['client_phone'],
                booking_id=info['booking_id'],
                booking_group_id=info['booking_group_id'],
                photographer_choice=info['photographer_choice'],
                total_price=info['total_price'],
                hours_in_group=info['hours_in_group'],
                has_discount=info['has_discount']
            ))
        else:
            result_bookings.append(schemas.BookingDetailResponse(
                hour=hour,
                is_booked=False
            ))
    
    return schemas.AdminDayStatusResponse(
        date=booking_date,
        has_bookings=len(booking_info) > 0,
        bookings=result_bookings
    )

@app.delete("/api/admin/bookings/{booking_id}")
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """Видалити ОДНУ годину бронювання (адмін може видаляти години окремо)"""
    
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Бронювання не знайдено")
    
    db.delete(booking)
    db.commit()
    
    return {
        "message": "Бронювання видалено",
        "booking_id": booking_id,
        "hour": booking.booking_hour
    }

@app.delete("/api/admin/bookings/group/{booking_group_id}")
def delete_booking_group(
    booking_group_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """Видалити ВСЮ ГРУПУ бронювань (всі години)"""
    
    bookings = db.query(models.Booking).filter(
        models.Booking.booking_group_id == booking_group_id
    ).all()
    
    if not bookings:
        raise HTTPException(status_code=404, detail="Група бронювань не знайдена")
    
    deleted_hours = [b.booking_hour for b in bookings]
    
    for booking in bookings:
        db.delete(booking)
    
    db.commit()
    
    return {
        "message": "Вся група видалена",
        "booking_group_id": booking_group_id,
        "deleted_hours": deleted_hours,
        "count": len(deleted_hours)
    }

@app.post("/api/monobank/webhook")
async def monobank_webhook(request: Request):
    """
    Webhook від Monobank коли клієнт оплатив
    """
    try:
        # Отримати дані від Monobank
        webhook_data = await request.json()
        
        logging.info(f"Monobank webhook received: {webhook_data}")
        
        # Перевірити підпис (в продакшні обов'язково!)
        # monobank.verify_signature(webhook_data)
        
        # Отримати статус
        status = webhook_data.get('status')
        invoice_id = webhook_data.get('invoiceId')
        reference = webhook_data.get('reference')  # booking_id
        
        if status == 'success':
            # Оплата успішна!
            booking_id = int(reference)
            
            # Оновити статус бронювання
            db = next(get_db())
            try:
                # Get booking
                booking = db.query(Booking).filter(Booking.id == booking_id).first()
                
                if booking:
                    # Update status
                    booking.status = 'paid'
                    booking.payment_status = 'paid'
                    db.commit()
                    
                    # Get client
                    client = db.query(Client).filter(Client.id == booking.client_id).first()
                    
                    # Get all bookings in group
                    group_id = booking.booking_group_id
                    if group_id:
                        bookings = db.query(Booking).filter(
                            Booking.booking_group_id == group_id
                        ).all()
                        # Update all in group
                        for b in bookings:
                            b.status = 'paid'
                            b.payment_status = 'paid'
                        db.commit()
                    else:
                        bookings = [booking]
                    
                    # Collect hours
                    hours = sorted([b.booking_hour for b in bookings])
                    hours_display = format_hours_display(hours)
                    
                    # Format services
                    services_summary = format_services_summary(booking)
                    
                    # Send confirmation to client
                    from telegram_service import bot
                    
                    client_message = f"""✅ <b>Оплата отримана!</b>

Дякуємо! Ваше бронювання підтверджено.

📅 <b>Дата:</b> {booking.booking_date.strftime('%d.%m.%Y')}
🕐 <b>Час:</b> {hours_display} ({len(hours)} год)

{services_summary}

💰 <b>Оплачено:</b> {booking.total_price} грн

━━━━━━━━━━━━━━━━

📍 <b>Адреса студії:</b>
м. Бровари, Київська область
провулок Івана Сокура, 1

📞 <b>Контакт:</b> @lonkilin

💡 Нагадування прийде за 24 год та за 3 год до сесії

Чекаємо вас! 📸"""
                    
                    await bot.send_message(
                        chat_id=client.telegram_id,
                        text=client_message,
                        parse_mode='HTML'
                    )
                    
                    # Notify admins
                    admin_message = f"""✅ <b>Оплачено онлайн!</b>

ID: #{booking_id}
👤 {client.name}
📞 {client.phone}

📅 {booking.booking_date.strftime('%d.%m.%Y')}
🕐 {hours_display} ({len(hours)} год)

{services_summary}

💰 Сума: {booking.total_price} грн
💳 Спосіб: Monobank (онлайн)

✅ Бронювання підтверджено автоматично"""
                    
                    await notify_admins(bot, admin_message)
                    
                    logging.info(f"Booking #{booking_id} marked as paid via Monobank")
                
            finally:
                db.close()
        
        return {"status": "ok"}
    
    except Exception as e:
        logging.error(f"Monobank webhook error: {e}")
        return {"status": "error", "message": str(e)}