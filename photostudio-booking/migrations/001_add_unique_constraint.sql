-- Migration: Add unique constraint to prevent double bookings
-- Date: 2025-12-15
-- Description: Ensures that the same date+hour combination can only be booked once

-- Add unique constraint
ALTER TABLE bookings 
ADD CONSTRAINT unique_booking_slot 
UNIQUE (booking_date, booking_hour);

-- This will prevent race conditions where two users try to book the same slot simultaneously
-- PostgreSQL will automatically reject the second INSERT with an IntegrityError
