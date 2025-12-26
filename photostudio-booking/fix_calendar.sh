#!/bin/bash

echo "🔧 ШВИДКЕ ВИПРАВЛЕННЯ: Оновлення статусів бронювань"
echo "=================================================="

echo ""
echo "📊 Поточний стан БД:"
docker exec photostudio-booking-db-1 psql -U photostudio -d photostudio_db -c "SELECT COUNT(*) as total FROM bookings;"

echo ""
echo "🔄 Додаємо колонку status (якщо немає)..."
docker exec photostudio-booking-db-1 psql -U photostudio -d photostudio_db -c "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'confirmed';"

echo ""
echo "🔄 Додаємо telegram поля..."
docker exec photostudio-booking-db-1 psql -U photostudio -d photostudio_db -c "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS telegram_user_id BIGINT;"
docker exec photostudio-booking-db-1 psql -U photostudio -d photostudio_db -c "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS confirmation_message_id BIGINT;"

echo ""
echo "✅ Оновлюємо ВСІ існуючі бронювання на 'confirmed'..."
docker exec photostudio-booking-db-1 psql -U photostudio -d photostudio_db -c "UPDATE bookings SET status = 'confirmed' WHERE status IS NULL OR status = '';"

echo ""
echo "📊 Результат:"
docker exec photostudio-booking-db-1 psql -U photostudio -d photostudio_db -c "SELECT status, COUNT(*) as count FROM bookings GROUP BY status;"

echo ""
echo "🔄 Перезапускаємо web service..."
docker-compose restart web

echo ""
echo "✅ ГОТОВО! Оновіть сторінку в браузері (Ctrl+Shift+R)"
