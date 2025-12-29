-- Migration: Add additional services support
-- Date: 2025-12-29

-- Add columns for additional services
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS people_count INTEGER;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS zone_choice VARCHAR(20);
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS animals_count INTEGER;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS background_choice VARCHAR(20);
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS total_price INTEGER DEFAULT 1000;

-- Update existing bookings with default values
UPDATE bookings SET total_price = 1000 WHERE total_price IS NULL;

-- Show result
SELECT 
    id, 
    booking_date, 
    status, 
    people_count, 
    zone_choice, 
    animals_count, 
    background_choice, 
    total_price 
FROM bookings 
LIMIT 5;
