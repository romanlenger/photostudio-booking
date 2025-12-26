"""
Database models for photostudio booking system
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
    """Booking model with Telegram confirmation support"""
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    booking_date = Column(Date, nullable=False, index=True)
    booking_hour = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    # NEW: Telegram confirmation fields
    status = Column(String(20), nullable=False, default="pending")
    # pending - created, awaiting confirmation
    # confirmed - user confirmed in Telegram
    # paid - payment received
    # cancelled - cancelled by user
    
    telegram_user_id = Column(BigInteger, nullable=True)
    confirmation_message_id = Column(BigInteger, nullable=True)
    
    # Relationships
    client = relationship("Client", back_populates="bookings")
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('booking_date', 'booking_hour', name='unique_booking_slot'),
    )
