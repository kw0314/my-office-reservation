# Copilot Instructions for My Office Reservation

## Overview
This is a **Django-based office room reservation system** with dual-view support (public + office kiosk). Core responsibility: manage room availability with time-slot reservations, recurring series, cancellations, and admin blocks.

### Key Architecture
- **Backend**: Django 6.0 + PostgreSQL (configured in `config/settings.py`)
- **Single app**: `reservations/` – handles models, API endpoints, HTML templates
- **Critical entry point**: `config/urls.py` routes all views
- **Timezone**: Fixed to **America/Chicago** (TZ_NAME = "America/Chicago") for all operations

## Domain Model & Key Entities

### Core Models (`reservations/models.py`)

**Room**: Office spaces (conference rooms, break rooms, etc.)
- Fields: `name`, `sort_order`, `location`, `active`
- Ordered by `sort_order` then `name`
- Example: "Conference Room A", "Break Area"

**Reservation**: Individual booking (30-minute slots, 09:00–20:00)
- **Status**: `confirmed` or `cancelled` (never deleted)
- **Recurrence**: `series_id` (UUID) groups recurring reservations
- **PIN-based cancellation**: 4-digit PIN stored as bcrypt hash (`cancel_pin_hash`)
- **Validation rules** (in `clean()` method):
  - Must be 30-min slot-aligned (`:00` or `:30` start/end)
  - Must not cross midnight (same local date only)
  - Must be within 09:00–20:00 (America/Chicago)
  - Must be ≥30 minutes duration
- **Brute-force protection**: `cancel_fail_count` + `cancel_locked_until` timestamp

**Block**: Admin-controlled time blocks (entire facility or specific room)
- Fields: `room` (nullable for facility-wide), `start_at`, `end_at`, `reason`
- Prevents reservations during blocked periods
- Indexed on `start_at`, `end_at`, and `(room, start_at)` for fast conflict checks

**AccessDevice**: Kiosk PCs with hashed device keys
- Fields: `label` (e.g., "Office-PC-1"), `device_key_hash`, `enabled`
- Used to track which device created a reservation

**AuditLog**: Immutable action ledger
- Tracks: actor type (device/admin), action (reservation_create, cancellation, etc.), IP, detail JSON
- Indexed on `at` and `action` for audit queries

## Critical Business Logic (`reservations/services.py`)

### Conflict Detection Pattern
```python
_check_conflicts(*, room: Room, start_at, end_at, exclude_reservation_id=None)
```
- Checks both **blocks** (facility-wide OR room-specific) AND existing **confirmed** reservations
- Raises `ValidationError` if overlap found
- Called before every reservation save

### Recurring Series Creation
```python
create_reservation(..., repeat_days: list[int] | None, repeat_until: date | None)
```
- **repeat_days**: list of weekdays (0=Sunday, 6=Saturday) – **project convention differs from Python's weekday()**
- **Safety cap**: `MAX_RECUR_OCCURRENCES = 60` to prevent bulk-insert timeouts
- Uses `@transaction.atomic` to ensure all-or-nothing series creation
- All instances in a series share same `series_id`, `cancel_pin`, and `title`
- Performs bulk validation before `bulk_create()` for performance

### Timezone Conversion Pattern
```python
# Always convert to local America/Chicago for business logic
local_dt = timezone.localtime(utc_dt, ZoneInfo("America/Chicago"))
local_date = local_dt.date()  # Use for date comparisons

# When returning to API, include timezone context
isoformat()  # Includes offset info
```

## API Endpoints (`reservations/urls.py`)

### Public API (read-only)
- `GET /view/` → HTML page showing public grid
- `GET /api/public/grid?date=YYYY-MM-DD` → JSON: rooms, reservations (title only), blocks

### Office Kiosk API (authenticated by device key)
- `GET /office/` → HTML page with full office view
- `GET /api/office/grid?date=YYYY-MM-DD` → JSON with internal notes, device labels
- `POST /api/office/reservations` → Create reservation (single or recurring)
- `PATCH /api/office/reservations/<rid>` → Update reservation (title, notes)
- `POST /api/office/reservations/<rid>/cancel` → Cancel with PIN verification

### Parameters & Validation
- **Date**: `?date=YYYY-MM-DD` (defaults to today, America/Chicago)
- **ISO Timestamps**: Accept formats with timezone offset or `Z` (UTC); parse via `_parse_dt()`
- **JSON Request Body** (create reservation):
  - `room_id`, `start_at`, `end_at` (ISO strings)
  - `title`, `note_internal` (strings)
  - `cancel_pin` (4-digit string)
  - `repeat_days` (optional: list of 0–6), `repeat_until` (optional: YYYY-MM-DD)

## Key Project Conventions

### 1. Weekday Numbering (Non-Standard)
Project uses **0=Sunday, 6=Saturday** (not Python's 0=Monday).
Function: `_our_dow(d: date) -> int` in services.py
```python
# Convert Python weekday to project convention
dow = (date.weekday() + 1) % 7
```

### 2. Slot Alignment Verification
Reservations must start/end at `:00` or `:30` minutes (30-min slots).
```python
@staticmethod
def _is_slot_aligned(dt) -> bool:
    return dt.minute in (0, 30) and dt.second == 0 and dt.microsecond == 0
```

### 3. PIN Storage (Bcrypt Hashing)
Never store raw PINs. Use Django's `make_password()` / `check_password()`:
```python
def set_cancel_pin(self, raw_pin: str) -> None:
    self.cancel_pin_hash = make_password(raw_pin)

def check_cancel_pin(self, raw_pin: str) -> bool:
    return check_password(raw_pin, self.cancel_pin_hash)
```

### 4. Same-Day Reservation Rule
Reservations cannot cross midnight (same local date requirement). See `_same_local_date()` in models.py.

### 5. Operating Hours (Hard Constraint)
All reservations must fit within 09:00–20:00 America/Chicago (defined as `OPEN_TIME`, `CLOSE_TIME` in models.py).

## Common Development Tasks

### Running & Testing
```bash
cd catechism
python manage.py runserver
python manage.py test reservations
python manage.py migrations
python manage.py migrate
```

### Database
- **Settings**: PostgreSQL (see `config/settings.py` DATABASES dict)
- **Credentials**: Hardcoded in settings (⚠️ security issue for production)
- **Migrations**: Django standard in `reservations/migrations/`

### Admin Panel
- Accessible at `/admin/` (Django default)
- Registered models: Room, Reservation, Block, AccessDevice, AuditLog
- Room: editable sort_order and active status inline
- Reservation: filterable by status/room, searchable by title/notes

## When Making Changes

1. **Always use `@transaction.atomic`** for operations affecting multiple rows (e.g., cancel series, create recurring).
2. **Validate with `full_clean()`** before save (Reservation model validates slots, hours, dates).
3. **Call `_check_conflicts()`** after validation but before inserting reservations.
4. **Log audit events** via `AuditLog.objects.create()` for cancellations, updates, device access.
5. **Use `timezone.localtime(..., TZ)`** for all date/time business logic in America/Chicago.
6. **Index queries**: Reservation queries typically filter by `(room, start_at)` or `(status, start_at)` – indexes exist.
7. **Handle `ValidationError`** from model cleaning and service functions – return appropriate HTTP 400 responses.

## File Reference Map

- **Models & Domain**: `reservations/models.py` (4 models + AuditLog)
- **Business Logic**: `reservations/services.py` (create_reservation, conflict checks, series handling)
- **Views & API**: `reservations/views.py` (8 endpoints, JSON + HTML rendering)
- **URL Routing**: `reservations/urls.py` (path definitions), `config/urls.py` (includes)
- **Admin UI**: `reservations/admin.py` (registered + configured)
- **Templates**: `reservations/templates/reservations/*.html` (public_view, office_view, detail pages)
- **Settings**: `config/settings.py` (Django config, DB connection, timezone TZ_NAME)
