from __future__ import annotations

import json
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from .models import Room, Reservation, Block
from . import services

TZ = ZoneInfo("America/Chicago")
OPEN_TIME = time(9, 0)
CLOSE_TIME = time(20, 0)
SLOT_MINUTES = 30

def office_rooms_view(request):
    rooms = Room.objects.all().order_by("id")
    return render(request, "reservations/office_rooms.html")

def office_room_detail_view(request, room_id: int):
    room = get_object_or_404(Room, id=room_id)
    return render(request, "reservations/office_room_detail.html", {"room": room})

def _parse_date(s: str | None) -> date:
    if not s:
        return timezone.localdate()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return timezone.localdate()


def _day_bounds(d: date):
    start = datetime.combine(d, OPEN_TIME, tzinfo=TZ)
    end = datetime.combine(d, CLOSE_TIME, tzinfo=TZ)
    return start, end


def _build_slots(d: date):
    start, end = _day_bounds(d)
    slots = []
    cur = start
    while cur < end:
        slots.append(cur)
        cur += timedelta(minutes=SLOT_MINUTES)
    return slots, start, end


def public_view(request: HttpRequest) -> HttpResponse:
    """
    Public HTML page.
    """
    d = _parse_date(request.GET.get("date"))
    return render(request, "reservations/public_view.html", {"selected_date": d.isoformat()})


def public_grid_api(request: HttpRequest) -> JsonResponse:
    """
    Returns all rooms + reservations + blocks for a given date (local America/Chicago).
    Public-safe fields only (title is allowed).
    """
    d = _parse_date(request.GET.get("date"))
    slots, day_start, day_end = _build_slots(d)

    rooms = list(Room.objects.filter(active=True).order_by("sort_order", "name").values("id", "name"))

    res_qs = Reservation.objects.filter(
        status=Reservation.STATUS_CONFIRMED,
        start_at__lt=day_end,
        end_at__gt=day_start,
        room__active=True,
    ).select_related("room")

    reservations = []
    for r in res_qs:
        reservations.append({
            "id": r.id,
            "room_id": r.room_id,
            "start_at": timezone.localtime(r.start_at, TZ).isoformat(),
            "end_at": timezone.localtime(r.end_at, TZ).isoformat(),
            "title": r.title,
        })

    block_qs = Block.objects.filter(
        start_at__lt=day_end,
        end_at__gt=day_start,
    ).select_related("room")

    blocks = []
    for b in block_qs:
        blocks.append({
            "id": b.id,
            "room_id": b.room_id,  # can be null => all rooms
            "start_at": timezone.localtime(b.start_at, TZ).isoformat(),
            "end_at": timezone.localtime(b.end_at, TZ).isoformat(),
            "reason": b.reason,
        })

    slot_labels = [s.strftime("%H:%M") for s in slots]

    return JsonResponse({
        "date": d.isoformat(),
        "open": OPEN_TIME.strftime("%H:%M"),
        "close": CLOSE_TIME.strftime("%H:%M"),
        "slot_minutes": SLOT_MINUTES,
        "slots": slot_labels,
        "rooms": rooms,
        "reservations": reservations,
        "blocks": blocks,
    })

def _parse_dt(iso_str: str) -> datetime:
    # accepts ISO with offset or Z
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(timezone.get_current_timezone())


def office_view(request: HttpRequest) -> HttpResponse:
    d = _parse_date(request.GET.get("date"))
    return render(request, "reservations/office_view.html", {"selected_date": d.isoformat()})


def office_grid_api(request: HttpRequest) -> JsonResponse:
    d = _parse_date(request.GET.get("date"))

    day_start = datetime.combine(d, OPEN_TIME, tzinfo=TZ)
    day_end = datetime.combine(d, CLOSE_TIME, tzinfo=TZ)

    rooms = list(Room.objects.filter(active=True).order_by("sort_order", "name").values("id", "name"))

    res_qs = Reservation.objects.filter(
        status=Reservation.STATUS_CONFIRMED,
        start_at__lt=day_end,
        end_at__gt=day_start,
        room__active=True,
    ).select_related("room")

    reservations = []
    for r in res_qs:
        reservations.append({
            "id": str(r.id),
            "room_id": str(r.room_id),
            "start_at": timezone.localtime(r.start_at, TZ).isoformat(),
            "end_at": timezone.localtime(r.end_at, TZ).isoformat(),
            "title": r.title,
            "note_internal": r.note_internal,
            "series_id": str(r.series_id) if r.series_id else None,
        })

    block_qs = Block.objects.filter(
        start_at__lt=day_end,
        end_at__gt=day_start,
    ).select_related("room")

    blocks = []
    for b in block_qs:
        blocks.append({
            "id": str(b.id),
            "room_id": (str(b.room_id) if b.room_id else None),
            "start_at": timezone.localtime(b.start_at, TZ).isoformat(),
            "end_at": timezone.localtime(b.end_at, TZ).isoformat(),
            "reason": b.reason,
        })

    # slots labels
    slots = []
    cur = day_start
    while cur < day_end:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=SLOT_MINUTES)

    return JsonResponse({
        "date": d.isoformat(),
        "open": OPEN_TIME.strftime("%H:%M"),
        "close": CLOSE_TIME.strftime("%H:%M"),
        "slot_minutes": SLOT_MINUTES,
        "slots": slots,
        "rooms": rooms,
        "reservations": reservations,
        "blocks": blocks,
    })


def _json(request: HttpRequest):
    raw = request.body or b""
    print("REQ CT=", request.META.get("CONTENT_TYPE"), "LEN=", len(raw))
    if raw:
        try:
            print("REQ RAW=", raw[:300])
        except Exception:
            pass
    try:
        return json.loads(raw.decode("utf-8") or "{}")
    except Exception as e:
        print("JSON PARSE ERROR:", repr(e))
        return {}


@csrf_exempt
@require_http_methods(["POST"])
def office_create_reservation(request: HttpRequest) -> JsonResponse:
    data = _json(request)
    print("CREAT payload:",data)
    try:
        room = Room.objects.get(id=data["room_id"])
        start_at = _parse_dt(data["start_at"])
        end_at = _parse_dt(data["end_at"])
        title = data.get("title", "")
        note = data.get("note_internal", "")
        cancel_pin = data.get("cancel_pin", "")

        # Optional recurrence fields
        repeat_days = data.get("repeat_days")
        repeat_until_raw = data.get("repeat_until")
        repeat_until = None
        if repeat_until_raw:
            try:
                repeat_until = datetime.strptime(repeat_until_raw, "%Y-%m-%d").date()
            except ValueError:
                raise ValidationError("Invalid repeat_until date.")

        created = services.create_reservation(
            room=room, start_at=start_at, end_at=end_at,
            title=title, note_internal=note, cancel_pin=cancel_pin,
            device=None, ip=request.META.get("REMOTE_ADDR"),
            repeat_days=repeat_days, repeat_until=repeat_until,
        )

        # Back-compat response
        if isinstance(created, tuple):
            series_id, items = created
            return JsonResponse({
                "ok": True,
                "series_id": str(series_id),
                "count": len(items),
                "ids": [str(x.id) for x in items],
                "id": str(items[0].id),
            })
        else:
            return JsonResponse({"ok": True, "id": str(created.id)})
    except (KeyError, Room.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Invalid room_id or payload."}, status=400)
    except ValidationError as e:
        return JsonResponse({"ok": False, "error": "; ".join(e.messages)}, status=400)


@csrf_exempt
@require_http_methods(["PATCH"])
def office_update_reservation(request: HttpRequest, rid) -> JsonResponse:
    data = _json(request)
    print("UPDATE payload:", data)
    try:
        room = Room.objects.get(id=data["room_id"])
        start_at = _parse_dt(data["start_at"])
        end_at = _parse_dt(data["end_at"])
        title = data.get("title", "")
        note = data.get("note_internal", "")
        new_pin = data.get("new_cancel_pin") or None

        # PIN verification required for edits/cancels
        cancel_pin = data.get("cancel_pin") or ""
        # load target reservation to verify PIN and potentially series id
        target = Reservation.objects.get(id=rid)
        now = timezone.now()
        if target.cancel_locked_until and now < target.cancel_locked_until:
            raise ValidationError("Cancel PIN locked. Try again later.")
        if not target.check_cancel_pin(cancel_pin):
            target.cancel_fail_count += 1
            if target.cancel_fail_count >= 3:
                target.cancel_locked_until = now + timedelta(minutes=5)
                target.cancel_fail_count = 0
            target.save(update_fields=["cancel_fail_count", "cancel_locked_until", "updated_at"])
            raise ValidationError("Invalid cancel PIN.")

        # scope handling: if series, apply series-wide update (title/note/new_pin)
        scope = str(data.get("scope") or "single").lower()
        if scope == "series":
            series_id = data.get("series_id") or (str(target.series_id) if target.series_id else None)
            if not series_id:
                raise ValidationError("No series_id available for series update.")
            # Pass room and the new start/end to allow shifting the whole series
            updated_items = services.update_reservation_series(
                reservation_id=rid,
                series_id=series_id,
                room=room,
                start_at=start_at,
                end_at=end_at,
                title=title,
                note_internal=note,
                new_cancel_pin=new_pin,
                device=None,
                ip=request.META.get("REMOTE_ADDR"),
            )
            print(f"Series update applied: {len(updated_items)} instances (series_id={series_id})")
            return JsonResponse({"ok": True, "count": len(updated_items)})

        # Single reservation update (PIN already verified above)
        services.update_reservation(
            reservation_id=rid,
            room=room, start_at=start_at, end_at=end_at,
            title=title, note_internal=note, new_cancel_pin=new_pin,
            device=None, ip=request.META.get("REMOTE_ADDR"),
        )
        return JsonResponse({"ok": True})
    except (KeyError, Room.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Invalid room_id or payload."}, status=400)
    except Reservation.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Reservation not found."}, status=404)
    except ValidationError as e:
        return JsonResponse({"ok": False, "error": "; ".join(e.messages)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def office_cancel_reservation(request: HttpRequest, rid) -> JsonResponse:
    data = _json(request)
    try:
        pin = data.get("cancel_pin", "")
        scope = data.get("scope", "single")
        services.cancel_reservation(
            reservation_id=rid,
            cancel_pin=pin,
            scope=("series" if str(scope).lower() == "series" else "single"),
            device=None, ip=request.META.get("REMOTE_ADDR"),
        )
        return JsonResponse({"ok": True})
    except Reservation.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Reservation not found."}, status=404)
    except ValidationError as e:
        return JsonResponse({"ok": False, "error": "; ".join(e.messages)}, status=400)

from django.shortcuts import render, get_object_or_404


