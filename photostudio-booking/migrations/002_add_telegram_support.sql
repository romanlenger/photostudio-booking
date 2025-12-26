-- Migration: Add Telegram confirmation support
-- Date: 2024-12-26

-- Add status column with default
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'confirmed';

-- Add telegram fields
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS telegram_user_id BIGINT;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS confirmation_message_id BIGINT;

-- Update ALL existing bookings to 'confirmed' status (they were already confirmed before)
UPDATE bookings SET status = 'confirmed' WHERE status IS NULL OR status = '';

-- Add index for faster queries
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_telegram_user ON bookings(telegram_user_id);

-- Show result
SELECT COUNT(*) as total_bookings, status, COUNT(*) as count_per_status 
FROM bookings 
GROUP BY status;
