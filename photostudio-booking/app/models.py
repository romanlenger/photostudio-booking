"""
Database models for photostudio booking system
UPDATED: Added booking_group_id and photographer_choice
"""
from sqlalchemy import Column, Integer, String, Date, ForeignKey, DateTime, func, UniqueConstraint, BigInteger
from sqlalchemy.orm import relationship
from .database import Base


class Client(Base):
    """Client model"""
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    bookings = relationship("Booking", back_populates="client")


class Booking(Base):
    """Booking model with Telegram confirmation support and multiple hours"""
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    booking_date = Column(Date, nullable=False, index=True)
    booking_hour = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    # NEW: Group multiple hours into single order
    booking_group_id = Column(String(50), nullable=True, index=True)
    # UUID to link multiple hour slots (e.g., 14:00, 15:00, 16:00)
    # All hours in same booking share this ID
    
    # Telegram confirmation fields
    status = Column(String(20), nullable=False, default="pending")
    # pending - created, awaiting confirmation
    # confirmed - user confirmed in Telegram
    # paid - payment received
    # cancelled - cancelled by user
    
    telegram_user_id = Column(BigInteger, nullable=True)
    confirmation_message_id = Column(BigInteger, nullable=True)
    
    # Additional services (selected on WEBSITE now!)
    people_count = Column(Integer, nullable=True)  # Кількість людей
    zone_choice = Column(String(20), nullable=True)  # light, dark, both
    animals_count = Column(Integer, nullable=True)  # Кількість тварин
    background_choice = Column(String(20), nullable=True)  # none, white, black, red
    
    # NEW: Photographer choice
    photographer_choice = Column(String(20), nullable=True, default='client')
    # 'client' - ваш фотограф (безкоштовно)
    # 'studio' - наш фотограф (+2000₴ за годину)
    
    total_price = Column(Integer, nullable=True, default=1000)  # Загальна ціна
    
    # Relationships
    client = relationship("Client", back_populates="bookings")
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('booking_date', 'booking_hour', name='unique_booking_slot'),
    )

class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = {'extend_existing': True}
    
    # ... existing fields ...
    
    # ADD THESE:
    monobank_invoice_id = Column(String, nullable=True)  # ID рахунку від Monobank
    payment_method = Column(String, default='manual')  # 'online' or 'manual'