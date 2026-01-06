-- Migration 004: Add multiple hours booking support and photographer choice
-- Date: 2026-01-05
-- Description: Adds booking_group_id for grouping multiple hour slots and photographer_choice field

-- Add booking group ID to link multiple hour bookings together
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS booking_group_id VARCHAR(50);

-- Add photographer choice field
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS photographer_choice VARCHAR(20) DEFAULT 'client';
-- Values: 'client' (ваш фотограф) or 'studio' (наш фотограф +2000₴/год)

-- Create index for faster group queries
CREATE INDEX IF NOT EXISTS idx_booking_group_id ON bookings(booking_group_id);

-- Add comment for documentation
COMMENT ON COLUMN bookings.booking_group_id IS 'UUID to group multiple hour slots into single order';
COMMENT ON COLUMN bookings.photographer_choice IS 'studio = our photographer (+2000/hour), client = bring your own (free)';

-- Example usage:
-- When client books 3 hours (14:00, 15:00, 16:00), system creates:
-- Row 1: booking_hour=14, booking_group_id='abc-123-uuid'
-- Row 2: booking_hour=15, booking_group_id='abc-123-uuid'  
-- Row 3: booking_hour=16, booking_group_id='abc-123-uuid'
-- All rows share same client_id, date, services, but different booking_hour
