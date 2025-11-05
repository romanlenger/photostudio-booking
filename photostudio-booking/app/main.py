from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import date, timedelta, datetime
import calendar

from . import models, schemas
from .database import engine, get_db

# Створення таблиць
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Photo Studio Booking System", version="1.0.0")

# Статичні файли
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Головна сторінка з календарем"""
    return FileResponse("static/index.html")

@app.post("/api/bookings/", response_model=schemas.BookingResponse, status_code=201)
def create_booking(
    booking: schemas.BookingCreate,
    db: Session = Depends(get_db)
):
    """Створити нове бронювання"""
    
    # Перевірити, чи година вже зайнята
    existing_booking = db.query(models.Booking).filter(
        models.Booking.booking_date == booking.booking_date,
        models.Booking.booking_hour == booking.booking_hour
    ).first()
    
    if existing_booking:
        raise HTTPException(status_code=400, detail="Ця година вже зайнята")
    
    # Знайти або створити клієнта
    client = db.query(models.Client).filter(
        models.Client.phone == booking.phone
    ).first()
    
    if not client:
        client = models.Client(name=booking.name, phone=booking.phone)
        db.add(client)
        db.flush()
    
    # Створити бронювання
    db_booking = models.Booking(
        client_id=client.id,
        booking_date=booking.booking_date,
        booking_hour=booking.booking_hour
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    
    return db_booking

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
    
    # Отримати всі бронювання за місяць
    bookings = db.query(models.Booking).filter(
        models.Booking.booking_date >= first_day,
        models.Booking.booking_date <= last_day
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
    
    bookings = db.query(models.Booking).filter(
        models.Booking.booking_date == booking_date
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

@app.delete("/api/bookings/{booking_id}", status_code=204)
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db)
):
    """Видалити бронювання"""
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Бронювання не знайдено")
    
    db.delete(booking)
    db.commit()
    
    return None

@app.get("/api/clients/", response_model=List[schemas.ClientResponse])
def get_clients(db: Session = Depends(get_db)):
    """Отримати всіх клієнтів"""
    clients = db.query(models.Client).all()
    return clients

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