# Telegram File Storage Bot

A feature-rich Telegram bot for storing and managing files in a private channel with MongoDB backend.

**Features:**
- Admin-only uploads with duplicate detection
- Download quota system (bandwidth + count limits)
- Shortlink token verification for downloads
- File organization (tags, rename, search, share)
- Auto-expiry with configurable timers
- Redis FSM state storage
- Sentry error tracking & monitoring
- Graceful shutdown handling

---

## Features

- **Admin-only uploads** — Only designated admins can upload files
- **Download quota system** — Per-user daily bandwidth and download count limits (resets at midnight UTC)
- **Unlimited downloads for admins** — Admins bypass quota restrictions
- **Shortlink token verification for downloads** — Non-admins must pass an ad (via shortlink) before downloading (configurable session duration)
- **Duplicate detection** — Automatically detects if you've already uploaded a file
- **File organization** — Tags, rename, search by filename or tag
- **File sharing** — Generate share codes for others to claim files
- **Auto-expiry** — Set files to expire after 1, 7, or 30 days
- **Admin dashboard** — View stats, manage download quotas, delete any file

---

## Requirements

- Python 3.11+
- MongoDB 7.0+
- Redis 7+ (for FSM state storage)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- A private Telegram channel for file storage
- Shortlink service (e.g., bit.ly, ouo.io, shorte.st) for ad-based verification

---

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/tg-file-bot.git
cd tg-bot-v2
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install production dependencies
pip install -r requirements.txt

# For development, install with dev extras
pip install -e ".[dev]"
```

### 2. Create Storage Channel

1. Create a private Telegram channel
2. Add your bot as an administrator with permission to post messages
3. Get the channel ID (should look like `-1001234567890`)

### 3. Configure Environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Telegram
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
STORAGE_CHANNEL_ID=-1001234567890

# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=tg_file_storage

# Redis (for FSM state storage)
REDIS_URI=redis://localhost:6379/0
REDIS_PASSWORD=              # Leave empty if no password

# Security
ALLOWED_USER_IDS=           # Empty = open access for all users
ADMIN_USER_IDS=123456789    # Comma-separated admin user IDs

# Quota (Download quota - resets daily at midnight UTC)
DEFAULT_QUOTA_MB=500        # Legacy - kept for backward compatibility
DEFAULT_BANDWIDTH_LIMIT_MB=500  # Daily bandwidth limit per user in MB (0 = unlimited)
DEFAULT_DOWNLOAD_LIMIT=0    # Daily download count limit (0 = unlimited)

# Token Verification (Shortlink-based ad verification)
VERIFY_EXPIRE_SECONDS=1200  # Token validity in seconds (default: 20 minutes)
SHORTLINK_URL=https://your-shortlink-service.com
SHORTLINK_API_KEY=your_api_key_here

# Auto-Expiry
DEFAULT_EXPIRY_DAYS=0       # 0 = no auto-expiry
EXPIRY_CLEANUP_INTERVAL=3600

# Monitoring & Error Tracking
SENTRY_DSN=                  # Sentry DSN for error tracking (leave empty to disable)
SENTRY_ENVIRONMENT=production  # Sentry environment (production, staging, development)
SENTRY_TRACES_SAMPLE_RATE=0.1  # Percentage of transactions to trace (0-1.0)

# App
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=2048
AUTO_DELETE_SECONDS=360
```

### 4. Run

```bash
python run.py
```

---

## Docker Deployment

### Quick Start

```bash
docker-compose up -d
```

This starts three services:
- **bot** - The Telegram bot application
- **mongo** - MongoDB 7.0 database
- **redis** - Redis 7 server for FSM state storage

### Production Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f bot

# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ data will be lost)
docker-compose down -v
```

### Health Checks

All services have health checks configured:
- **Bot**: Python process check
- **MongoDB**: ping check
- **Redis**: ping check

View health status:
```bash
docker-compose ps
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=bot --cov-report=html

# Run specific test file
pytest tests/database/test_file_repo.py

# Run with verbose output
pytest -v

# Run only fast tests
pytest -m "not slow"
```

### Test Coverage

The test suite includes **103 test cases** covering:
- Repository layer (FileRepository, QuotaRepository)
- Data models (FileRecord, UserQuotaRecord)
- Utilities (file helpers, keyboard builders)
- Handlers (upload functionality)

Test files are located in the `tests/` directory.

---

## Usage

### Token Verification System

Non-admin users must complete a shortlink ad verification before downloading files:

1. When a user tries to download a file (`/get`, inline button, or `/claim`), they receive a verification prompt
2. The bot sends a shortlink that users must open and view (completing an ad)
3. After passing the ad, users can download files for the configured duration (default: 20 minutes)
4. Admins bypass this verification entirely

### User Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message |
| `/help` | Show all commands |
| `/list` | Browse your files (paginated) |
| `/get <id>` | Retrieve a file by ID |
| `/search <query>` | Search files by filename |
| `/tag <tag>` | Find files by tag |
| `/rename <id>` | Rename a file |
| `/delete <id>` | Delete a file |
| `/share <id>` | Generate a share code |
| `/claim <code>` | Claim a shared file (requires verification) |
| `/mystats` | View your download quota usage |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/admin` | Open admin dashboard |
| `/setquota <user_id> <mb>` | Set user quota (0 = unlimited) |
| `/delfile <record_id>` | Force-delete any file |
| `/userinfo <user_id>` | View user stats |

### File Actions

After uploading, interactive buttons allow you to:
- **Tag** — Add tags for organization
- **Rename** — Change display name
- **Share** — Generate share code
- **Expiry** — Set auto-delete timer
- **Delete** — Remove file

---

## Architecture

```
bot/
├── main.py                    # Entry point with Redis, Sentry, graceful shutdown
├── config.py                  # Settings (Pydantic)
├── database/
│   ├── connection.py          # MongoDB connection
│   ├── redis_connection.py    # Redis FSM storage manager
│   └── repositories/
│       ├── file_repo.py       # File CRUD operations
│       └── quota_repo.py      # Quota tracking & verification
├── handlers/
│   ├── upload.py              # File upload (admin-only)
│   ├── download.py            # File retrieval & management
│   ├── admin.py               # Admin panel
│   └── common.py              # /start, /help
├── middlewares/
│   └── auth.py                # Allowlist middleware
├── models/
│   └── file_record.py         # Data models
├── tasks/
│   └── expiry_task.py         # Background expiry cleanup
└── utils/
    ├── file_utils.py          # Helpers
    ├── keyboards.py           # Inline keyboards
    └── states.py              # FSM states
```

---

## Tech Stack

### Core
- **aiogram 3.7** — Telegram Bot framework
- **Motor 3.4** — Async MongoDB driver
- **Redis 7** — FSM state storage
- **Pydantic 2.7** — Settings & data validation

### Storage
- **MongoDB 7.0** — Primary database
- **Redis 7** — FSM state storage with AOF persistence

### Monitoring
- **Sentry SDK 1.40** — Error tracking and performance monitoring

### Testing
- **pytest 7.4** — Test framework
- **pytest-asyncio** — Async test support
- **pytest-cov** — Coverage reporting
- **pytest-mock** — Mocking utilities

### Code Quality
- **black** — Code formatting
- **flake8** — Linting
- **mypy** — Type checking
- **isort** — Import sorting

---

## Production Hardening

This bot includes production-ready features:

### ✅ Implemented
- **Comprehensive test coverage** — 103 test cases across critical components
- **Redis FSM storage** — Persistent state with MemoryStorage fallback
- **Sentry monitoring** — Error tracking and performance traces
- **Graceful shutdown** — Proper signal handling and resource cleanup
- **Health checks** — Docker health checks for all services
- **Structured logging** — Better observability and debugging
- **Pinned dependencies** — All versions locked for reproducibility

### 📊 Key Metrics
- **Test coverage**: 103 test cases
- **Uptime**: Graceful shutdown ensures clean state
- **Monitoring**: Sentry integration for error tracking
- **Scalability**: Redis FSM supports multiple bot instances

For detailed hardening documentation, see `PRODUCTION_HARDENING.md`.

---

## Troubleshooting

### Redis Connection Issues

If Redis fails to start:
```bash
# Check Redis logs
docker-compose logs redis

# Restart Redis
docker-compose restart redis

# Bot will automatically fallback to MemoryStorage
```

### Sentry Not Working

- Verify SENTRY_DSN is set correctly
- Check Sentry dashboard for incoming errors
- Check logs for "Sentry initialized" message

### Tests Failing

```bash
# Ensure MongoDB and Redis are running (for database tests)
docker-compose up -d mongo redis

# Run with verbose output
pytest -v

# Skip connection tests if services unavailable
pytest -v -k "not (mongo or redis)"
```

---

## License

MIT
