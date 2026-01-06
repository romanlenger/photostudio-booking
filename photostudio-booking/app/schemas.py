from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from typing import Optional, List

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
    """Create booking with multiple hours and all services"""
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    booking_date: date
    booking_hours: List[int] = Field(..., min_items=1)  # NEW: Multiple hours [14, 15, 16]
    
    # Services (selected on website!)
    people_count: int = Field(default=4, ge=1, le=20)
    zone_choice: str = Field(default='light')  # light, dark, both
    animals_count: int = Field(default=0, ge=0, le=10)
    background_choice: str = Field(default='none')  # none, white, black, red
    photographer_choice: str = Field(default='client')  # NEW: client, studio
    
    total_price: int = Field(..., gt=0)  # Calculated on frontend
    
    @validator('booking_date')
    def date_not_in_past(cls, v):
        if v < date.today():
            raise ValueError('Не можна бронювати дату в минулому')
        return v
    
    @validator('booking_hours')
    def validate_hours(cls, v):
        """Validate hours are in working range and unique"""
        if not v:
            raise ValueError('Треба обрати хоча б одну годину')
        if len(v) != len(set(v)):
            raise ValueError('Години не можуть повторюватись')
        for hour in v:
            if hour < 9 or hour > 21:
                raise ValueError('Години мають бути між 9 та 21')
        return sorted(v)
    
    @validator('zone_choice')
    def validate_zone(cls, v):
        if v not in ['light', 'dark', 'both']:
            raise ValueError('Невірний вибір зони')
        return v
    
    @validator('background_choice')
    def validate_background(cls, v):
        if v not in ['none', 'white', 'black', 'red']:
            raise ValueError('Невірний вибір фону')
        return v
    
    @validator('photographer_choice')
    def validate_photographer(cls, v):
        if v not in ['client', 'studio']:
            raise ValueError('Невірний вибір фотографа')
        return v

class BookingResponse(BaseModel):
    id: int
    booking_date: date
    booking_hour: int
    booking_group_id: Optional[str] = None  # NEW
    created_at: datetime
    client: ClientResponse
    telegram_link: Optional[str] = None
    status: str = "pending"
    people_count: Optional[int] = None
    zone_choice: Optional[str] = None
    animals_count: Optional[int] = None
    background_choice: Optional[str] = None
    photographer_choice: Optional[str] = None  # NEW
    total_price: Optional[int] = None
    
    class Config:
        from_attributes = True

class BookingGroupResponse(BaseModel):
    """Response for grouped bookings"""
    booking_group_id: str
    booking_ids: List[int]
    hours: List[int]
    client_name: str
    client_phone: str
    booking_date: date
    status: str
    people_count: int
    zone_choice: str
    animals_count: int
    background_choice: str
    photographer_choice: str
    total_price: int
    telegram_link: Optional[str] = None

class DayStatusResponse(BaseModel):
    date: date
    has_bookings: bool
    available_hours: list[int]
    booked_hours: list[int]

# Admin schemas
class LoginRequest(BaseModel):
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class BookingDetailResponse(BaseModel):
    """Детальна інформація про бронювання для адміна"""
    hour: int
    is_booked: bool
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    booking_id: Optional[int] = None
    booking_group_id: Optional[str] = None  # NEW
    photographer_choice: Optional[str] = None  # NEW
    total_price: Optional[int] = None  # NEW: Total price
    hours_in_group: Optional[int] = None  # NEW: How many hours in this group
    has_discount: Optional[bool] = None  # NEW: Whether 10% discount applied

class AdminDayStatusResponse(BaseModel):
    """Статус дня з деталями для адміна"""
    date: date
    has_bookings: bool
    bookings: List[BookingDetailResponse]
