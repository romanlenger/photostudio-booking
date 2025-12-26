from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from datetime import date, timedelta, datetime
import calendar
import os

from . import models, schemas
from .database import engine, get_db
from .auth import verify_password, create_access_token, get_current_admin
from .telegram_service import telegram_notifier

# Створення таблиць
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Photo Studio Booking System", version="1.0.0")

# Статичні файли
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Головна сторінка з календарем (для користувачів)"""
    return FileResponse("static/index.html")

@app.get("/admin")
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

@app.post("/api/bookings/", response_model=schemas.BookingResponse, status_code=201)
async def create_booking(
    booking: schemas.BookingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Створити нове бронювання з переадресацією на Telegram"""
    
    # Перевірити, чи година вже зайнята
    existing_booking = db.query(models.Booking).filter(
        models.Booking.booking_date == booking.booking_date,
        models.Booking.booking_hour == booking.booking_hour,
        models.Booking.status.in_(['pending', 'confirmed', 'paid'])
    ).first()
    
    if existing_booking:
        raise HTTPException(status_code=400, detail="Ця година вже зайнята")
    
    try:
        # Знайти або створити клієнта
        client = db.query(models.Client).filter(
            models.Client.phone == booking.phone
        ).first()
        
        if not client:
            client = models.Client(name=booking.name, phone=booking.phone)
            db.add(client)
            db.flush()
        
        # Створити бронювання зі статусом pending
        db_booking = models.Booking(
            client_id=client.id,
            booking_date=booking.booking_date,
            booking_hour=booking.booking_hour,
            status="pending"
        )
        db.add(db_booking)
        db.commit()
        db.refresh(db_booking)
        
        # 🔗 Створити Telegram deep link
        bot_username = os.getenv("BOT_USERNAME", "your_bot_username")
        telegram_link = f"https://t.me/{bot_username}?start=booking_{db_booking.id}"
        
        # 🤖 ВІДПРАВИТИ TELEGRAM СПОВІЩЕННЯ АДМІНАМ (в фоновому режимі)
        background_tasks.add_task(
            telegram_notifier.send_new_booking_notification,
            client_name=booking.name,
            client_phone=booking.phone,
            booking_date=str(booking.booking_date),
            booking_hour=booking.booking_hour,
            booking_id=db_booking.id
        )
        
        # Додати telegram_link до відповіді
        response = schemas.BookingResponse.from_orm(db_booking)
        response.telegram_link = telegram_link
        
        return response
        
    except IntegrityError:
        # ЗАХИСТ: Якщо двоє одночасно намагаються забронювати - база відхилить другого
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Ця година щойно була заброньована іншим користувачем. Оберіть іншу годину."
        )

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
    
    # Отримати всі АКТИВНІ бронювання за місяць (pending, confirmed, paid)
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
    
    # Робочі години студії (наприклад, з 9 до 21)
    WORK_HOURS = list(range(9, 21))
    
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
    
    # Вибрати тільки активні бронювання (pending, confirmed, paid)
    bookings = db.query(models.Booking).filter(
        models.Booking.booking_date == booking_date,
        models.Booking.status.in_(['pending', 'confirmed', 'paid'])
    ).all()
    
    # Робочі години студії (з 9 до 21)
    WORK_HOURS = list(range(9, 21))
    booked_hours = [b.booking_hour for b in bookings]
    available_hours = [h for h in WORK_HOURS if h not in booked_hours]
    
    return schemas.DayStatusResponse(
        date=booking_date,
        has_bookings=len(booked_hours) > 0,
        available_hours=available_hours,
        booked_hours=booked_hours
    )

# Admin-only endpoints
@app.get("/api/admin/day/{booking_date}", response_model=schemas.AdminDayStatusResponse)
def get_admin_day_status(
    booking_date: date,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Отримати детальний статус дня для адміна (показуємо всі бронювання)"""
    
    # Адмін бачить ВСІ бронювання (включно з cancelled)
    bookings = db.query(models.Booking).filter(
        models.Booking.booking_date == booking_date
    ).all()
    
    # Робочі години студії (з 9 до 21)
    WORK_HOURS = list(range(9, 21))
    
    # Створити словник бронювань по годинах
    bookings_dict = {b.booking_hour: b for b in bookings}
    
    # Створити детальний список всіх годин
    booking_details = []
    for hour in WORK_HOURS:
        if hour in bookings_dict:
            booking = bookings_dict[hour]
            booking_details.append(schemas.BookingDetailResponse(
                hour=hour,
                is_booked=True,
                client_name=booking.client.name,
                client_phone=booking.client.phone,
                booking_id=booking.id
            ))
        else:
            booking_details.append(schemas.BookingDetailResponse(
                hour=hour,
                is_booked=False
            ))
    
    return schemas.AdminDayStatusResponse(
        date=booking_date,
        has_bookings=len(bookings) > 0,
        bookings=booking_details
    )

@app.get("/api/admin/bookings/", response_model=List[schemas.BookingResponse])
def get_admin_bookings(
    start_date: date = Query(None),
    end_date: date = Query(None),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Отримати всі бронювання для адміна (з деталями)"""
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

@app.delete("/api/bookings/{booking_id}", status_code=204)
async def delete_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Видалити бронювання (тільки для адміна)"""
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Бронювання не знайдено")
    
    # Зберегти дані для сповіщення перед видаленням
    client_name = booking.client.name
    booking_date = str(booking.booking_date)
    booking_hour = booking.booking_hour
    
    db.delete(booking)
    db.commit()
    
    # 🤖 ВІДПРАВИТИ TELEGRAM СПОВІЩЕННЯ про скасування
    background_tasks.add_task(
        telegram_notifier.send_booking_cancelled_notification,
        client_name=client_name,
        booking_date=booking_date,
        booking_hour=booking_hour,
        booking_id=booking_id
    )
    
    return None

@app.get("/api/clients/", response_model=List[schemas.ClientResponse])
def get_clients(db: Session = Depends(get_db)):
    """Отримати всіх клієнтів"""
    clients = db.query(models.Client).all()
    return clients

@app.post("/api/admin/test-telegram")
async def test_telegram(admin: dict = Depends(get_current_admin)):
    """Відправити тестове Telegram повідомлення (тільки для адміна)"""
    
    # Отримати chat_ids з налаштувань
    if not telegram_notifier.admin_chat_ids:
        raise HTTPException(
            status_code=400,
            detail="Telegram chat IDs не налаштовано. Додайте TELEGRAM_ADMIN_CHAT_IDS в .env"
        )
    
    success = False
    for chat_id in telegram_notifier.admin_chat_ids:
        result = await telegram_notifier.send_test_message(chat_id)
        if result:
            success = True
    
    if success:
        return {"message": "Тестове повідомлення відправлено успішно!"}
    else:
        raise HTTPException(status_code=500, detail="Помилка відправки повідомлення")

@app.get("/api/clients/{client_id}", response_model=schemas.ClientResponse)
def get_client(
    client_id: int,
    db: Session = Depends(get_db)
):
    """Отримати клієнта по ID"""
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    
    if not client:
        raise HTTPException(status_code=404, detail="Клієнт не знайдений")
    
    return client