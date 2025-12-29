# 📸 Photo Studio Booking System

A complete booking system for photo studios with Telegram bot integration, automatic payment processing, and additional services selection.

## ✨ Features

### 🌐 Web Interface
- **Interactive Calendar** - Visual date and time slot selection
- **Real-time Availability** - Instant booking status updates
- **Responsive Design** - Works perfectly on desktop and mobile
- **Admin Panel** - Manage bookings and view statistics

### 🤖 Telegram Bot
- **Automated Booking Confirmation** - Clients confirm bookings via Telegram
- **Multi-step Service Selection** - Interactive questionnaire for additional services
- **Automatic Price Calculation** - Dynamic pricing based on selected options
- **Payment Processing** - Integrated payment details and screenshot upload
- **Admin Notifications** - Real-time alerts for new bookings and payments
- **Persistent Menu** - Quick access to website and Instagram

### 💰 Additional Services System
- **People Count** - Up to 4 included, +100 UAH per additional person
- **Photo Zones** - Light, Dark, or Both (+500 UAH)
- **Animals** - 1 included, +100 UAH per additional animal
- **Backgrounds** - White/Black/Red (+100 UAH each)
- **Total Price Display** - Automatic calculation and summary

### 🔐 Security & Reliability
- **PostgreSQL Database** - Reliable data storage
- **Docker Deployment** - Easy setup and scaling
- **Environment Variables** - Secure configuration management
- **SSL/HTTPS Ready** - Secure connections

---

## 🛠️ Tech Stack

- **Backend:** FastAPI (Python 3.11)
- **Bot:** python-telegram-bot
- **Database:** PostgreSQL 15
- **Deployment:** Docker + Docker Compose
- **Web Server:** Nginx (for production)
- **SSL:** Let's Encrypt (Certbot)

---

## 📋 Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+ (or use Docker)
- Telegram Bot Token
- VPS/Server for production

---

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/romanlenger/photostudio-booking.git
cd photostudio-booking
```

### 2. Create Environment File

Create `.env` file in the root directory:

```bash
# Database
DB_PASSWORD=your_secure_password_here

# Telegram Bot
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_IDS=123456789,987654321

# URLs
WEBSITE_URL=http://localhost:8000
INSTAGRAM_URL=https://instagram.com/your_profile

# Studio Info (optional)
STUDIO_RULES="Your studio rules here"
```

### 3. Run with Docker

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Initialize Database

```bash
# Run migrations
docker exec photostudio-booking-db-1 psql -U photostudio -d photostudio_db -f /migrations/001_initial.sql
docker exec photostudio-booking-db-1 psql -U photostudio -d photostudio_db -f /migrations/002_add_telegram.sql
docker exec photostudio-booking-db-1 psql -U photostudio -d photostudio_db -f /migrations/003_add_additional_services.sql
```

### 5. Access the Application

- **Website:** http://localhost:8000
- **Admin Panel:** http://localhost:8000/admin.html
- **Telegram Bot:** Find your bot on Telegram

---

## 📁 Project Structure

```
photostudio-booking/
├── app/                      # FastAPI application
│   ├── __init__.py
│   ├── main.py              # Main application
│   ├── models.py            # Database models
│   ├── database.py          # Database connection
│   └── routers/             # API routes
├── bot.py                    # Telegram bot
├── static/                   # Frontend files
│   ├── index.html           # Booking page
│   └── admin.html           # Admin panel
├── migrations/               # SQL migrations
│   ├── 001_initial.sql
│   ├── 002_add_telegram.sql
│   └── 003_add_additional_services.sql
├── docker-compose.yml        # Docker orchestration
├── Dockerfile               # Docker image
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (create manually)
└── README.md                # This file
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_PASSWORD` | PostgreSQL password | `supersecret123` |
| `BOT_TOKEN` | Telegram bot token | `123456:ABC-DEF...` |
| `ADMIN_IDS` | Telegram admin IDs | `123456789,987654321` |
| `WEBSITE_URL` | Website URL | `https://yourdomain.com` |
| `INSTAGRAM_URL` | Instagram profile | `https://instagram.com/studio` |
| `STUDIO_RULES` | Studio rules text | `1. Be on time...` |

### Telegram Bot Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the bot token
4. Add token to `.env` file
5. Get your Telegram ID from [@userinfobot](https://t.me/userinfobot)
6. Add your ID to `ADMIN_IDS` in `.env`

---

## 💳 Payment Configuration

Edit payment details in `bot.py`:

```python
card_number = "5168757412345678"
card_display = "5168 7574 1234 5678"
```

And in the payment message:

```python
payment = f"""💳 Payment Details:

<code>{card_display}</code>
Recipient Name

Amount: {price} UAH
"""
```

---

## 🌐 Production Deployment

### On VPS (Ubuntu 22.04)

#### 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
```

#### 2. Clone & Configure

```bash
git clone https://github.com/romanlenger/photostudio-booking.git
cd photostudio-booking
nano .env  # Add your configuration
```

#### 3. Start Services

```bash
docker-compose up -d
```

#### 4. Setup Nginx

```bash
sudo apt install nginx

# Create config
sudo nano /etc/nginx/sites-available/photostudio
```

Add:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable config
sudo ln -s /etc/nginx/sites-available/photostudio /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

#### 5. Setup SSL (HTTPS)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

---

## 🔄 Updates

To update the application on the server:

```bash
# SSH to server
ssh root@your-server-ip

# Navigate to project
cd photostudio-booking

# Pull latest changes
git pull

# Restart services
docker-compose restart bot web

# Or rebuild if needed
docker-compose down
docker-compose build
docker-compose up -d
```

---

## 📊 Database Schema

### Tables

- **clients** - Customer information (name, phone, email)
- **bookings** - Booking records with dates, times, and status
- **Additional service fields:**
  - `people_count` - Number of people
  - `zone_choice` - Selected photo zone
  - `animals_count` - Number of animals
  - `background_choice` - Background type
  - `total_price` - Calculated total price

---

## 🐛 Troubleshooting

### Bot not responding

```bash
# Check bot logs
docker-compose logs -f bot

# Restart bot
docker-compose restart bot
```

### Database connection issues

```bash
# Check database logs
docker-compose logs -f db

# Verify database is running
docker-compose ps
```

### Port already in use

```bash
# Check what's using port 8000
sudo lsof -i :8000

# Kill the process or change port in docker-compose.yml
```

---

## 📝 API Endpoints

### Public Endpoints

- `GET /` - Booking page
- `GET /admin.html` - Admin panel
- `GET /available_slots?date=YYYY-MM-DD` - Get available time slots
- `POST /book` - Create new booking

### Database Endpoints

- `GET /bookings` - List all bookings
- `GET /clients` - List all clients

---

## 🎨 Customization

### Change Studio Name

Edit `static/index.html` and `static/admin.html`

### Modify Pricing

Edit `bot.py` in the `calculate_price()` function:

```python
def calculate_price(people, zone, animals, bg):
    price = 1000  # Base price
    if people > 4: 
        price += (people - 4) * 100  # Per person
    if zone == 'both': 
        price += 500  # Both zones
    if animals > 1: 
        price += (animals - 1) * 100  # Per animal
    if bg != 'none': 
        price += 100  # Background
    return price
```

### Add More Services

1. Add fields to database in `app/models.py`
2. Create migration SQL file
3. Add questions in `bot.py`
4. Update `calculate_price()` function

---

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check existing documentation
- Review logs: `docker-compose logs`

---

## 📄 License

This project is private. All rights reserved.

---

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/)
- [python-telegram-bot](https://python-telegram-bot.org/)
- [PostgreSQL](https://www.postgresql.org/)
- [Docker](https://www.docker.com/)

---

## 📈 Future Features

- [ ] Online payment integration
- [ ] Email notifications
- [ ] Calendar export (iCal)
- [ ] Multi-language support
- [ ] Booking history for clients
- [ ] Review system

---

**Made with ❤️ for photo studios**
