from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.translation import gettext as _
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Chicago")


def format_datetime(dt):
    local_dt = timezone.localtime(dt, TZ)
    return local_dt.strftime("%Y-%m-%d %H:%M")


def send_reservation_status_email(reservations, event_type):
    """
    reservations: a single Reservation instance or a list/QuerySet of Reservation instances
    event_type: 'confirmed' | 'modified' | 'cancelled'
    """
    if not getattr(settings, "RESERVATION_EMAILS_ENABLED", False):
        logger.info("Reservation email disabled; skipped event '%s'.", event_type)
        return

    if not isinstance(reservations, (list, tuple)) and not hasattr(reservations, "exists"):
        reservations = [reservations]

    reservations = list(reservations)
    if not reservations:
        return

    # We assume all reservations in the batch belong to the same person and room/title (for series).
    first_res = reservations[0]

    if not first_res.email:
        return

    subject_map = {
        "confirmed": _("[사무실 예약] 신청하신 예약이 확정되었습니다."),
        "modified": _("[사무실 예약] 예약 정보가 변경되었습니다."),
        "cancelled": _("[사무실 예약] 예약이 취소(반려)되었습니다."),
    }

    subject = subject_map.get(event_type, _("[사무실 예약] 안내 메시지"))

    room_name = first_res.room.name
    title = first_res.title
    count = len(reservations)

    try:
        reservations.sort(key=lambda x: x.start_at)
    except Exception:
        pass

    start_str = format_datetime(first_res.start_at)
    end_str = format_datetime(first_res.end_at)

    if count > 1:
        date_summary = _("%(start)s ~ %(end)s 외 %(extra_count)s건 (총 %(count)s건)") % {
            "start": start_str,
            "end": end_str[11:],
            "extra_count": count - 1,
            "count": count,
        }
    else:
        date_summary = f"{start_str} ~ {end_str[11:]}"

    details = _("- 교리실: %(room)s\n- 일시: %(date)s\n- 예약명: %(title)s") % {
        "room": room_name,
        "date": date_summary,
        "title": title,
    }

    if event_type == "confirmed":
        message = _(
            "안녕하세요,\n\n"
            "신청하신 다음 예약이 확정되었습니다.\n\n"
            "%(details)s\n\n"
            "감사합니다."
        ) % {"details": details}
    elif event_type == "modified":
        message = _(
            "안녕하세요,\n\n"
            "신청하신 예약의 상세 정보가 관리자에 의해 변경되었습니다.\n\n"
            "%(details)s\n\n"
            "변경된 예약 정보를 확인해 주세요.\n\n"
            "감사합니다."
        ) % {"details": details}
    else:
        message = _(
            "안녕하세요,\n\n"
            "신청하신 예약이 관리자에 의해 취소 또는 반려 처리되었습니다.\n\n"
            "%(details)s\n\n"
            "감사합니다."
        ) % {"details": details}

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[first_res.email],
            fail_silently=False,
        )
        logger.info("Email sent successfully to %s for event '%s' (%s reservations)", first_res.email, event_type, count)
    except Exception as e:
        logger.error("Failed to send email to %s: %s", first_res.email, e)
