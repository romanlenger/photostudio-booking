from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from typing import Optional

class ClientBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)

class ClientCreate(ClientBase):
    pass

class ClientResponse(ClientBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class BookingCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    booking_date: date
    booking_hour: int = Field(..., ge=0, le=23)
    
    @validator('booking_date')
    def date_not_in_past(cls, v):
        if v < date.today():
            raise ValueError('Не можна бронювати дату в минулому')
        return v

class BookingResponse(BaseModel):
    id: int
    booking_date: date
    booking_hour: int
    created_at: datetime
    client: ClientResponse
    
    class Config:
        from_attributes = True

class DayStatusResponse(BaseModel):
    date: date
    has_bookings: bool
    available_hours: list[int]
    booked_hours: list[int]
