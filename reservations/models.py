#from django.db import models

# Create your models here.
from __future__ import annotations

from datetime import time, timedelta, datetime
from zoneinfo import ZoneInfo
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
import logging
import uuid

TZ_NAME = "America/Chicago"

OPEN_TIME = time(9, 0)   # 09:00
CLOSE_TIME = time(20, 0) # 20:00
SLOT_MINUTES = 30


class Room(models.Model):
    name = models.CharField(max_length=80, unique=True)
    sort_order = models.PositiveIntegerField(default=0)
    location = models.CharField(max_length=120, blank=True, default="")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class AccessDevice(models.Model):
    """
    Office PCs (3~5). Store only hashed device key.
    """
    label = models.CharField(max_length=80, unique=True)  # Office-PC-1...
    device_key_hash = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_device_key(self, raw_key: str) -> None:
        self.device_key_hash = make_password(raw_key)

    def check_device_key(self, raw_key: str) -> bool:
        return check_password(raw_key, self.device_key_hash)

    def __str__(self) -> str:
        return self.label


class Block(models.Model):
    """
    Admin blocks time: whole facility (room is NULL) or specific room.
    """
    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.CASCADE)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["start_at"]),
            models.Index(fields=["end_at"]),
            models.Index(fields=["room", "start_at"]),
        ]

    def clean(self):
        if self.start_at >= self.end_at:
            raise ValidationError("Block end time must be after start time.")

    def __str__(self) -> str:
        scope = self.room.name if self.room else "ALL ROOMS"
        return f"[{scope}] {self.start_at} ~ {self.end_at} {self.reason}".strip()


class Reservation(models.Model):
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()

    # Public-visible title
    title = models.CharField(max_length=120)

    # Internal note (never public)
    note_internal = models.TextField(blank=True, default="")

    # 4-digit cancel PIN hash (store hash only)
    cancel_pin_hash = models.CharField(max_length=255)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CONFIRMED)

    created_by_device = models.ForeignKey(AccessDevice, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Recurrence grouping (nullable for one-off reservations)
    # If set, all reservations with the same series_id are treated as one repeating series.
    series_id = models.UUIDField(null=True, blank=True, db_index=True)

    # Cancel brute-force protection
    cancel_fail_count = models.PositiveIntegerField(default=0)
    cancel_locked_until = models.DateTimeField(null=True, blank=True)

    # Color of the reservation block (CSS hex/color)
    color = models.CharField(max_length=20, default="#e3f2fd")

    class Meta:
        indexes = [
            models.Index(fields=["room", "start_at"]),
            models.Index(fields=["room", "end_at"]),
            models.Index(fields=["status", "start_at"]),
        ]

    # ---- PIN helpers ----
    def set_cancel_pin(self, raw_pin: str) -> None:
        if not (raw_pin and raw_pin.isdigit() and len(raw_pin) == 4):
            raise ValidationError("Cancel PIN must be exactly 4 digits.")
        self.cancel_pin_hash = make_password(raw_pin)

    def check_cancel_pin(self, raw_pin: str) -> bool:
        return check_password(raw_pin, self.cancel_pin_hash)

    # ---- Validation helpers ----
    @staticmethod
    def _is_slot_aligned(dt) -> bool:
        return dt.minute in (0, 30) and dt.second == 0 and dt.microsecond == 0

    @staticmethod
    def _same_local_date(a, b) -> bool:
        la = timezone.localtime(a)
        lb = timezone.localtime(b)
        return la.date() == lb.date()

    @staticmethod
    def _within_hours(start_dt, end_dt) -> bool:
        """Return True if the reservation is within operating hours (America/Chicago)."""
        tz = ZoneInfo(TZ_NAME)

        # Normalize to America/Chicago for business-hour checks
        ls = start_dt.astimezone(tz)
        le = end_dt.astimezone(tz)

        # Build tz-aware open/close datetimes for the same local date as the start
        open_dt = datetime.combine(ls.date(), OPEN_TIME, tzinfo=tz)
        close_dt = datetime.combine(ls.date(), CLOSE_TIME, tzinfo=tz)

        # Must be within [09:00, 20:00]
        return (open_dt <= ls) and (le <= close_dt)

    def clean(self):
        if self.start_at >= self.end_at:
            raise ValidationError("End time must be after start time.")

        # 최소 30분
        if self.end_at - self.start_at < timedelta(minutes=SLOT_MINUTES):
            raise ValidationError("Reservation must be at least 30 minutes.")

        # 30분 단위 정렬
        if not self._is_slot_aligned(self.start_at) or not self._is_slot_aligned(self.end_at):
            raise ValidationError("Start/end must be aligned to 30-minute slots (:00 or :30).")

        # 같은 날짜 안에서만 (운영 편의)
        if not self._same_local_date(self.start_at, self.end_at):
            raise ValidationError("Reservation must not cross midnight (same day only).")

        # 운영시간 내
        if not self._within_hours(self.start_at, self.end_at):

            logger = logging.getLogger(__name__)

            logger.warning("CREATE payload start_at=%s end_at=%s", self.start_at, self.end_at)
            logger.warning("tzinfo start=%s end=%s", getattr(start_at, "tzinfo", None), getattr(end_at, "tzinfo", None))
            logger.warning("as local start=%s end=%s", start_at.astimezone(), end_at.astimezone() if hasattr(start_at,"astimezone") else "naive")
            logger.warning("open=%s close=%s", OPEN_TIME, CLOSE_TIME)
            raise ValidationError("Reservation must be within operating hours 09:00–20:00.")

        # Cancel PIN hash must exist
        if not self.cancel_pin_hash:
            raise ValidationError("Cancel PIN is required.")

    def __str__(self) -> str:
        return f"{self.room} {self.start_at}~{self.end_at} {self.title}"


class AuditLog(models.Model):
    ACTOR_DEVICE = "device"
    ACTOR_ADMIN = "admin"
    ACTOR_CHOICES = [
        (ACTOR_DEVICE, "Device"),
        (ACTOR_ADMIN, "Admin"),
    ]

    actor_type = models.CharField(max_length=10, choices=ACTOR_CHOICES)
    actor_label = models.CharField(max_length=80, blank=True, default="")
    action = models.CharField(max_length=40)
    reservation = models.ForeignKey(Reservation, null=True, blank=True, on_delete=models.SET_NULL)
    ip = models.GenericIPAddressField(null=True, blank=True)
    detail = models.JSONField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["at"]), models.Index(fields=["action"])]

    def __str__(self) -> str:
        return f"{self.at} {self.actor_type}:{self.actor_label} {self.action}"

