from django.core.mail import send_mail
from zoneinfo import ZoneInfo
from django.utils import timezone
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
    if not isinstance(reservations, (list, tuple)) and not hasattr(reservations, 'exists'):
        reservations = [reservations]
        
    reservations = list(reservations)
    if not reservations:
        return
        
    # We assume all reservations in the batch belong to the same person and room/title (for series)
    first_res = reservations[0]
    
    if not first_res.email:
        return
        
    subject_map = {
        'confirmed': "[사무실 예약] 신청하신 예약이 확정되었습니다.",
        'modified': "[사무실 예약] 예약 정보가 변경되었습니다.",
        'cancelled': "[사무실 예약] 예약이 취소(반려)되었습니다."
    }
    
    subject = subject_map.get(event_type, "[사무실 예약] 안내 메시지")
    
    room_name = first_res.room.name
    title = first_res.title
    count = len(reservations)
    
    # Sort by start_at if possible
    try:
        reservations.sort(key=lambda x: x.start_at)
    except Exception:
        pass
        
    start_str = format_datetime(first_res.start_at)
    end_str = format_datetime(first_res.end_at)
    
    if count > 1:
        date_summary = f"{start_str} ~ {end_str[11:]} 외 {count - 1}건 (총 {count}건)"
    else:
        date_summary = f"{start_str} ~ {end_str[11:]}"
    
    if event_type == 'confirmed':
        message = (
            f"안녕하세요,\n\n"
            f"신청하신 다음 예약이 확정되었습니다.\n\n"
            f"- 교리실: {room_name}\n"
            f"- 일시: {date_summary}\n"
            f"- 단체명: {title}\n\n"
            f"감사합니다."
        )
    elif event_type == 'modified':
        message = (
            f"안녕하세요,\n\n"
            f"신청하신 예약의 상세 정보가 관리자에 의해 변경되었습니다.\n\n"
            f"- 교리실: {room_name}\n"
            f"- 일시: {date_summary}\n"
            f"- 단체명: {title}\n\n"
            f"변경된 예약 정보를 확인해 주세요.\n\n"
            f"감사합니다."
        )
    else:  # cancelled
        message = (
            f"안녕하세요,\n\n"
            f"신청하신 예약이 관리자에 의해 취소 또는 반려 처리되었습니다.\n\n"
            f"- 교리실: {room_name}\n"
            f"- 일시: {date_summary}\n"
            f"- 단체명: {title}\n\n"
            f"감사합니다."
        )
        
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[first_res.email],
            fail_silently=False,
        )
        logger.info(f"Email sent successfully to {first_res.email} for event '{event_type}' ({count} reservations)")
    except Exception as e:
        logger.error(f"Failed to send email to {first_res.email}: {e}")
