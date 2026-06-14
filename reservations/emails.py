from django.core.mail import send_mail
from zoneinfo import ZoneInfo
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Chicago")

def format_datetime(dt):
    local_dt = timezone.localtime(dt, TZ)
    return local_dt.strftime("%Y-%m-%d %H:%M")

def send_reservation_status_email(reservation, event_type):
    """
    event_type: 'confirmed' | 'modified' | 'cancelled'
    """
    if not reservation.email:
        return
        
    subject_map = {
        'confirmed': "[사무실 예약] 신청하신 예약이 확정되었습니다.",
        'modified': "[사무실 예약] 예약 정보가 변경되었습니다.",
        'cancelled': "[사무실 예약] 예약이 취소(반려)되었습니다."
    }
    
    subject = subject_map.get(event_type, "[사무실 예약] 안내 메시지")
    
    room_name = reservation.room.name
    start_str = format_datetime(reservation.start_at)
    end_str = format_datetime(reservation.end_at)
    title = reservation.title
    
    if event_type == 'confirmed':
        message = (
            f"안녕하세요,\n\n"
            f"신청하신 다음 예약이 확정되었습니다.\n\n"
            f"- 교리실: {room_name}\n"
            f"- 일시: {start_str} ~ {end_str}\n"
            f"- 단체명: {title}\n\n"
            f"감사합니다."
        )
    elif event_type == 'modified':
        message = (
            f"안녕하세요,\n\n"
            f"신청하신 예약의 상세 정보가 관리자에 의해 변경되었습니다.\n\n"
            f"- 교리실: {room_name}\n"
            f"- 일시: {start_str} ~ {end_str}\n"
            f"- 단체명: {title}\n\n"
            f"변경된 예약 정보를 확인해 주세요.\n\n"
            f"감사합니다."
        )
    else:  # cancelled
        message = (
            f"안녕하세요,\n\n"
            f"신청하신 예약이 관리자에 의해 취소 또는 반려 처리되었습니다.\n\n"
            f"- 교리실: {room_name}\n"
            f"- 일시: {start_str} ~ {end_str}\n"
            f"- 단체명: {title}\n\n"
            f"감사합니다."
        )
        
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[reservation.email],
            fail_silently=False,
        )
        logger.info(f"Email sent successfully to {reservation.email} for event '{event_type}'")
    except Exception as e:
        logger.error(f"Failed to send email to {reservation.email}: {e}")
