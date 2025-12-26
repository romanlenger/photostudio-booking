# 🔧 ВИПРАВЛЕННЯ: Зникли дні в календарі

## 🎯 ПРОБЛЕМА:

Після оновлення зникли дні з календаря, тому що:
1. Старі бронювання в БД не мають поля `status`
2. API фільтрує тільки активні статуси (pending, confirmed, paid)
3. NULL статус = не показується

---

## ✅ ШВИДКЕ ВИПРАВЛЕННЯ:

### Варіант 1: Автоматичний скрипт (РЕКОМЕНДОВАНО)

```bash
cd ~/photostudio-booking

# Запусти скрипт
./fix_calendar.sh

# Оновіть браузер
Ctrl + Shift + R
```

---

### Варіант 2: Вручну через SQL

```bash
# Підключись до БД
docker exec -it photostudio-booking-db-1 psql -U photostudio -d photostudio_db

# Виконай команди:
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'confirmed';
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS telegram_user_id BIGINT;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS confirmation_message_id BIGINT;

UPDATE bookings SET status = 'confirmed' WHERE status IS NULL OR status = '';

# Перевір
SELECT status, COUNT(*) FROM bookings GROUP BY status;

# Вийди
\q

# Перезапусти web
docker-compose restart web
```

---

### Варіант 3: Міграція (якщо не робив раніше)

```bash
docker exec -it photostudio-booking-db-1 psql -U photostudio -d photostudio_db

# Виконай міграцію
\i /migrations/002_add_telegram_support.sql

\q

docker-compose restart web
```

---

## ✅ ЩО ВИПРАВЛЕНО В КОДІ:

### 1. app/main.py - фільтр по статусам:

```python
# Календар - тільки активні
bookings = db.query(models.Booking).filter(
    models.Booking.booking_date >= first_day,
    models.Booking.booking_date <= last_day,
    models.Booking.status.in_(['pending', 'confirmed', 'paid'])  # ← ДОДАНО
).all()

# День - тільки активні  
bookings = db.query(models.Booking).filter(
    models.Booking.booking_date == booking_date,
    models.Booking.status.in_(['pending', 'confirmed', 'paid'])  # ← ДОДАНО
).all()

# Адмін - всі (включно з cancelled)
bookings = db.query(models.Booking).filter(
    models.Booking.booking_date == booking_date
).all()  # Без фільтру - адмін бачить все
```

### 2. Міграція оновлена:

```sql
-- Всі старі бронювання отримують status = 'confirmed'
ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT 'confirmed';
UPDATE bookings SET status = 'confirmed' WHERE status IS NULL;
```

---

## 🔍 ПЕРЕВІРКА:

### 1. Перевір БД:

```bash
docker exec photostudio-booking-db-1 psql -U photostudio -d photostudio_db -c "SELECT status, COUNT(*) FROM bookings GROUP BY status;"
```

**Маєш побачити:**
```
  status   | count 
-----------+-------
 confirmed |    15
 pending   |     2
(2 rows)
```

### 2. Перевір API:

Відкрий в браузері:
```
http://192.168.88.26:8000/api/calendar/2024/12
```

**Маєш побачити JSON:**
```json
[
  {
    "date": "2024-12-01",
    "has_bookings": true,
    "available_hours": [9, 10, 12, ...],
    "booked_hours": [11, 13, ...]
  },
  ...
]
```

### 3. Перевір календар:

Відкрий:
```
http://192.168.88.26:8000
```

**Маєш побачити:**
- ✅ Всі дні місяця
- ✅ Дні з бронюваннями темніші
- ✅ Можна натиснути на день

---

## 🎯 ЛОГІКА СТАТУСІВ:

```
pending    → Створено, чекає підтвердження в Telegram
confirmed  → Підтверджено, чекає оплату
paid       → Оплачено
cancelled  → Скасовано (не показується на календарі)
```

**Клієнт бачить:** pending + confirmed + paid  
**Адмін бачить:** всі, включно з cancelled

---

## ❓ ЯКЩО НЕ ПРАЦЮЄ:

### Логи:

```bash
# Подивись логи web
docker-compose logs web

# Подивись логи БД
docker-compose logs db

# Подивись всі контейнери
docker ps
```

### Перезапуск:

```bash
docker-compose restart web
docker-compose restart db

# Або все разом
docker-compose restart
```

### Повна пересборка:

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

**ЗРОБИ fix_calendar.sh І КАЛЕНДАР ЗАПРАЦЮЄ! ✅**
