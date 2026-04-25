from __future__ import annotations

from datetime import timedelta, datetime, date
from zoneinfo import ZoneInfo
import calendar as _cal
import uuid
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.hashers import make_password

from .models import Reservation, Block, Room, AccessDevice, AuditLog

TZ = ZoneInfo("America/Chicago")

# Safety cap: recurring series can create many rows and heavy conflict checks.
# Keep this small to avoid timeouts and accidental large writes.
MAX_RECUR_OCCURRENCES = 60


def _our_dow(d: date) -> int:
    """Return 0=Sunday..6=Saturday (project convention) for a local date."""
    return (d.weekday() + 1) % 7


def _intervals_overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and a_end > b_start


def _overlaps(qs, start_at, end_at):
    return qs.filter(start_at__lt=end_at, end_at__gt=start_at)


def _check_conflicts(*, room: Room, start_at, end_at, exclude_reservation_id=None):
    # blocks overlap (room-specific or ALL)
    blocks = Block.objects.filter(room__isnull=True) | Block.objects.filter(room=room)
    if _overlaps(blocks, start_at, end_at).exists():
        raise ValidationError("Time is blocked (unavailable).")

    # existing reservations overlap
    existing = Reservation.objects.filter(room=room, status=Reservation.STATUS_CONFIRMED)
    if exclude_reservation_id:
        existing = existing.exclude(id=exclude_reservation_id)
    if _overlaps(existing, start_at, end_at).exists():
        raise ValidationError("Time overlaps with an existing reservation.")


def _add_months(d: date, months: int) -> date:
    """Add months to a date, clamping to end of month."""
    m = d.month - 1 + months
    year = d.year + m // 12
    month = m % 12 + 1
    return date(year, month, min(d.day, _cal.monthrange(year, month)[1]))


def _generate_repeat_dates(
    *, start_date: date, repeat_until: date,
    repeat_type: str, repeat_days: list[int],
    repeat_interval: int = 1,
    repeat_weeks_of_month: list[int] | None = None,
) -> list[date]:
    """Generate candidate dates for a recurring series.

    repeat_type  : 'weekly' | 'monthly' | 'monthly_custom'
    repeat_days  : [0..6]  0=Sun..6=Sat  (weekly / monthly_custom)
    repeat_interval : every N weeks (weekly only, default 1)
    repeat_weeks_of_month: [1..5] 5=last (monthly_custom only)
    """
    result: list[date] = []

    if repeat_type == "monthly":
        m = 0
        while True:
            d = _add_months(start_date, m)
            if d > repeat_until:
                break
            if d >= start_date:
                result.append(d)
                if len(result) > MAX_RECUR_OCCURRENCES:
                    raise ValidationError(f"성성 가능한 최대 횟수를 초과합니다 (max {MAX_RECUR_OCCURRENCES}).")
            m += 1

    elif repeat_type == "monthly_custom":
        if not repeat_days or not repeat_weeks_of_month:
            return []
        cur_y, cur_m = start_date.year, start_date.month
        while date(cur_y, cur_m, 1) <= repeat_until:
            for our_dow in sorted(repeat_days):
                py_wd = (our_dow - 1) % 7  # our Sun=0 -> Python Sun=6
                day_nums = [row[py_wd] for row in _cal.monthcalendar(cur_y, cur_m) if row[py_wd]]
                for wom in sorted(repeat_weeks_of_month):
                    idx = -1 if wom == 5 else wom - 1
                    if 0 <= idx < len(day_nums) or wom == 5:
                        d = date(cur_y, cur_m, day_nums[idx])
                        if start_date <= d <= repeat_until:
                            result.append(d)
            cur_m += 1
            if cur_m > 12:
                cur_y += 1
                cur_m = 1
        result = sorted(set(result))
        if len(result) > MAX_RECUR_OCCURRENCES:
            raise ValidationError(f"성성 가능한 최대 횟수를 초과합니다 (max {MAX_RECUR_OCCURRENCES}).")

    else:  # weekly (handles weekly / biweekly / N-weekly / weekdays)
        if not repeat_days:
            return []
        start_of_week = start_date - timedelta(days=_our_dow(start_date))
        cur = start_date
        while cur <= repeat_until:
            weeks = (cur - start_of_week).days // 7
            if weeks % repeat_interval == 0 and _our_dow(cur) in repeat_days:
                result.append(cur)
                if len(result) > MAX_RECUR_OCCURRENCES:
                    raise ValidationError(
                        f"성성 가능한 최대 횟수를 초과합니다 (max {MAX_RECUR_OCCURRENCES})."
                    )
            cur += timedelta(days=1)

    return result



@transaction.atomic
def create_reservation(*, room: Room, start_at, end_at, title: str, note_internal: str,
                       cancel_pin: str, color: str = "#e3f2fd",
                       device: AccessDevice | None, ip: str | None,
                       repeat_days: list[int] | None = None,
                       repeat_until: date | None = None,
                       repeat_interval: int = 1,
                       repeat_type: str = "weekly",
                       repeat_weeks_of_month: list[int] | None = None):
    """Create a single or recurring reservation.

    repeat_type: 'weekly'|'monthly'|'monthly_custom'
    repeat_days: [0..6] 0=Sun (weekly/monthly_custom)
    repeat_interval: every N weeks (weekly, default 1)
    repeat_weeks_of_month: [1..5] 5=last (monthly_custom)
    """
    title_s = title.strip()
    note_s = note_internal.strip()
    duration = end_at - start_at

    def _make_oneoff(instance_start):
        r = Reservation(
            room=room,
            start_at=instance_start,
            end_at=instance_start + duration,
            title=title_s,
            note_internal=note_s,
            color=color,
            created_by_device=device,
        )
        r.set_cancel_pin(cancel_pin)
        r.full_clean()
        _check_conflicts(room=room, start_at=r.start_at, end_at=r.end_at)
        r.save()
        return r

    # Determine if this is a recurring reservation
    is_recurring = bool(repeat_days) or repeat_type == "monthly"
    if not is_recurring:
        r = _make_oneoff(start_at)
        AuditLog.objects.create(
            actor_type=AuditLog.ACTOR_DEVICE if device else AuditLog.ACTOR_ADMIN,
            actor_label=(device.label if device else "office"),
            action="reservation_create",
            reservation=r,
            ip=ip,
            detail={"room": room.name, "start_at": str(r.start_at), "end_at": str(r.end_at), "title": r.title},
        )
        return r

    # --- recurring ---
    if repeat_until is None:
        raise ValidationError("반복 예약에는 종료일이 필요합니다.")

    if repeat_days:
        repeat_days = sorted({int(x) for x in repeat_days})
        for d in repeat_days:
            if d < 0 or d > 6:
                raise ValidationError("repeat_days must be within 0..6 (0=Sunday).")

    local_start = timezone.localtime(start_at, TZ)
    start_date = local_start.date()
    if repeat_until < start_date:
        raise ValidationError("종료일은 시작일 이후여야 합니다.")
    if (repeat_until - start_date).days > 730:
        raise ValidationError("반복 범위가 너무 큽니다 (max 2년).")

    local_t = local_start.timetz().replace(tzinfo=None)
    candidate_dates = _generate_repeat_dates(
        start_date=start_date,
        repeat_until=repeat_until,
        repeat_type=repeat_type,
        repeat_days=repeat_days or [],
        repeat_interval=max(1, repeat_interval),
        repeat_weeks_of_month=repeat_weeks_of_month,
    )

    if not candidate_dates:
        raise ValidationError("생성되는 예약이 없습니다. 반복 설정을 확인해 주세요.")


    # Build timezone-aware instance intervals
    tz_cur = timezone.get_current_timezone()
    instance_starts = []
    for d0 in candidate_dates:
        instance_local = datetime.combine(d0, local_t, tzinfo=TZ)
        instance_starts.append(instance_local.astimezone(tz_cur))

    instance_ends = [s + duration for s in instance_starts]
    min_start = min(instance_starts)
    max_end = max(instance_ends)

    # Preload potential conflicts once (fast path for <= MAX_RECUR_OCCURRENCES)
    blocks_qs = (Block.objects.filter(room__isnull=True) | Block.objects.filter(room=room))
    blocks_qs = blocks_qs.filter(start_at__lt=max_end, end_at__gt=min_start)
    block_intervals = [(b.start_at, b.end_at) for b in blocks_qs.only("start_at", "end_at")]

    existing_qs = Reservation.objects.filter(
        room=room,
        status=Reservation.STATUS_CONFIRMED,
        start_at__lt=max_end,
        end_at__gt=min_start,
    ).only("start_at", "end_at")
    existing_intervals = [(x.start_at, x.end_at) for x in existing_qs]

    # Validate conflicts in Python (small N)
    for s, e in zip(instance_starts, instance_ends):
        for bs, be in block_intervals:
            if _intervals_overlap(s, e, bs, be):
                raise ValidationError("Time is blocked (unavailable).")
        for rs, re in existing_intervals:
            if _intervals_overlap(s, e, rs, re):
                raise ValidationError("Time overlaps with an existing reservation.")

    series_id = uuid.uuid4()
    pin_hash = make_password(cancel_pin)

    instance_objs: list[Reservation] = []
    for s in instance_starts:
        instance_objs.append(
            Reservation(
                room=room,
                start_at=s,
                end_at=s + duration,
                title=title_s,
                note_internal=note_s,
                color=color,
                created_by_device=device,
                series_id=series_id,
                cancel_pin_hash=pin_hash,
            )
        )

    # bulk insert (Postgres supports returning IDs)
    Reservation.objects.bulk_create(instance_objs)

    created = instance_objs

    AuditLog.objects.create(
        actor_type=AuditLog.ACTOR_DEVICE if device else AuditLog.ACTOR_ADMIN,
        actor_label=(device.label if device else "office"),
        action="reservation_create_series",
        reservation=created[0],
        ip=ip,
        detail={
            "room": room.name,
            "series_id": str(series_id),
            "count": len(created),
            "repeat_days": repeat_days,
            "repeat_until": str(repeat_until),
            "start_time": local_start.strftime("%H:%M"),
            "duration_minutes": int(duration.total_seconds() // 60),
            "title": title_s,
        },
    )
    return series_id, created


@transaction.atomic
def update_reservation(*, reservation_id, room: Room, start_at, end_at, title: str,
                       note_internal: str, color: str = None, new_cancel_pin: str | None,
                       device: AccessDevice | None, ip: str | None):
    r = Reservation.objects.select_for_update().get(id=reservation_id)

    if r.status != Reservation.STATUS_CONFIRMED:
        raise ValidationError("Cannot update a cancelled reservation.")

    r.room = room
    r.start_at = start_at
    r.end_at = end_at
    r.title = title.strip()
    r.note_internal = note_internal.strip()
    if color:
        r.color = color

    if new_cancel_pin:
        r.set_cancel_pin(new_cancel_pin)

    r.full_clean()
    _check_conflicts(room=room, start_at=start_at, end_at=end_at, exclude_reservation_id=r.id)

    r.save()

    AuditLog.objects.create(
        actor_type=AuditLog.ACTOR_DEVICE if device else AuditLog.ACTOR_ADMIN,
        actor_label=(device.label if device else "office"),
        action="reservation_update",
        reservation=r,
        ip=ip,
        detail={"room": room.name, "start_at": str(start_at), "end_at": str(end_at), "title": r.title},
    )
@transaction.atomic
def update_reservation_series(*, reservation_id, series_id: str, room: Room | None,
                              start_at=None, end_at=None,
                              title: str | None, note_internal: str | None, color: str | None = None,
                              new_cancel_pin: str | None, device: AccessDevice | None, ip: str | None):
    """
    Update all reservations in a series (title, note, cancel pin, and optionally time).
    
    If start_at/end_at provided: apply NEW duration to anchor instance, then shift others maintaining their spacing.
    
    - `series_id` can be passed explicitly; `reservation_id` is used to locate the primary row and validate PIN prior to calling this service.
    """
    # Load all confirmed reservations in the series
    qs = Reservation.objects.select_for_update().filter(series_id=series_id, status=Reservation.STATUS_CONFIRMED).order_by('start_at')
    items = list(qs)
    if not items:
        raise ValidationError("No series reservations found.")

    series_ids = [r.id for r in items]

    # Determine target room for conflict checks: use provided room or current room of series
    room_to_use = room or items[0].room

    # If start_at/end_at provided, compute delta to shift all instances
    delta = None
    anchor = None
    if start_at is not None and end_at is not None:
        # use the reservation_id instance as anchor
        try:
            anchor = next(r for r in items if str(r.id) == str(reservation_id) or r.id == reservation_id)
        except StopIteration:
            anchor = items[0]
        
        # Delta is the time shift: how much to move the anchor's start from its original to new start
        delta = start_at - anchor.start_at

        # compute proposed new intervals for all instances:
        # - Anchor gets new start_at and new end_at
        # - Others shift by delta, keeping their original duration
        new_starts = []
        new_ends = []
        
        for r in items:
            if r.id == anchor.id:
                # Anchor instance gets the exact new times
                new_starts.append(start_at)
                new_ends.append(end_at)
            else:
                # Other instances shift by delta, keep their original duration
                new_starts.append(r.start_at + delta)
                new_ends.append(r.end_at + delta)
        
        min_start = min(new_starts)
        max_end = max(new_ends)

        # preload potential conflicts excluding this series
        blocks_qs = (Block.objects.filter(room__isnull=True) | Block.objects.filter(room=room_to_use))
        blocks_qs = blocks_qs.filter(start_at__lt=max_end, end_at__gt=min_start)
        block_intervals = [(b.start_at, b.end_at) for b in blocks_qs.only('start_at', 'end_at')]

        existing_qs = Reservation.objects.filter(
            room=room_to_use,
            status=Reservation.STATUS_CONFIRMED,
            start_at__lt=max_end,
            end_at__gt=min_start,
        ).exclude(id__in=series_ids).only('start_at', 'end_at')
        existing_intervals = [(x.start_at, x.end_at) for x in existing_qs]

        # Validate conflicts for each proposed interval
        for s_new, e_new in zip(new_starts, new_ends):
            for bs, be in block_intervals:
                if _intervals_overlap(s_new, e_new, bs, be):
                    raise ValidationError("Time is blocked (unavailable) for series update.")
            for rs, re in existing_intervals:
                if _intervals_overlap(s_new, e_new, rs, re):
                    raise ValidationError("Time overlaps with an existing reservation for series update.")

    # Apply updates to each instance
    updated = []
    new_duration = end_at - start_at if (end_at is not None and start_at is not None) else None
    
    for r in items:
        if room is not None:
            r.room = room_to_use
        if title is not None:
            r.title = title.strip()
        if note_internal is not None:
            r.note_internal = note_internal.strip()
        if color is not None:
            r.color = color
        if new_cancel_pin:
            r.set_cancel_pin(new_cancel_pin)
        
        # Apply time shift if delta was computed
        if delta is not None and anchor is not None:
            if r.id == anchor.id:
                # Anchor instance gets the exact new times
                r.start_at = start_at
                r.end_at = end_at
            else:
                # Other instances shift by delta, applying new duration to each
                r.start_at = r.start_at + delta
                r.end_at = r.start_at + new_duration

        # validate each instance (slot alignment, same-day, operating hours)
        r.full_clean()
        r.save()
        updated.append(r)

    AuditLog.objects.create(
        actor_type=AuditLog.ACTOR_DEVICE if device else AuditLog.ACTOR_ADMIN,
        actor_label=(device.label if device else "office"),
        action="reservation_update_series",
        reservation=updated[0],
        ip=ip,
        detail={
            "series_id": str(series_id),
            "count": len(updated),
            "title": title,
        },
    )
    return updated


@transaction.atomic
def cancel_reservation(*, reservation_id, cancel_pin: str, device: AccessDevice | None, ip: str | None,
                       scope: str = "single"):
    r = Reservation.objects.select_for_update().get(id=reservation_id)

    if r.status != Reservation.STATUS_CONFIRMED:
        return r  # already cancelled

    now = timezone.now()
    if r.cancel_locked_until and now < r.cancel_locked_until:
        raise ValidationError("Cancel PIN locked. Try again later.")

    if not r.check_cancel_pin(cancel_pin):
        r.cancel_fail_count += 1
        if r.cancel_fail_count >= 3:
            r.cancel_locked_until = now + timedelta(minutes=5)
            r.cancel_fail_count = 0
        r.save(update_fields=["cancel_fail_count", "cancel_locked_until", "updated_at"])
        raise ValidationError("Invalid cancel PIN.")

    # Determine cancel targets
    targets = [r]
    if scope == "series" and r.series_id:
        targets = list(
            Reservation.objects.select_for_update().filter(
                series_id=r.series_id,
                status=Reservation.STATUS_CONFIRMED,
            )
        )

    for t in targets:
        if t.status != Reservation.STATUS_CONFIRMED:
            continue
        t.status = Reservation.STATUS_CANCELLED
        t.cancel_fail_count = 0
        t.cancel_locked_until = None
        t.save(update_fields=["status", "cancel_fail_count", "cancel_locked_until", "updated_at"])

    AuditLog.objects.create(
        actor_type=AuditLog.ACTOR_DEVICE if device else AuditLog.ACTOR_ADMIN,
        actor_label=(device.label if device else "office"),
        action="reservation_cancel_series" if (scope == "series" and r.series_id) else "reservation_cancel",
        reservation=r,
        ip=ip,
        detail={
            "room": r.room.name,
            "start_at": str(r.start_at),
            "end_at": str(r.end_at),
            "title": r.title,
            "scope": scope,
            "series_id": str(r.series_id) if r.series_id else None,
            "count": len(targets),
        },
    )
    return r

