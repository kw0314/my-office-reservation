from django.contrib import admin, messages
from django.http import Http404, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, OuterRef, Subquery, Case, When, Value, IntegerField
from django.template.response import TemplateResponse
from django.utils import timezone
from zoneinfo import ZoneInfo

from .models import Room, Reservation, Block, AccessDevice, AuditLog
from .emails import send_reservation_status_email

TZ = ZoneInfo("America/Chicago")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order", "location", "active", "requires_approval")
    list_editable = ("sort_order", "active", "requires_approval")
    search_fields = ("name", "location")


class SeriesFilter(admin.SimpleListFilter):
    """Filter reservations by series (recurring) vs single."""
    title = "예약 유형"
    parameter_name = "series_type"

    def lookups(self, request, model_admin):
        return [
            ("series", "반복 예약 (시리즈)"),
            ("single", "단건 예약"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "series":
            return queryset.filter(series_id__isnull=False)
        if self.value() == "single":
            return queryset.filter(series_id__isnull=True)
        return queryset


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "room_link", "start_at_local", "end_at_local", "title_link", "status_badge",
        "series_info", "approve_button",
    )
    list_display_links = None
    list_filter = ("status", "room", SeriesFilter)
    search_fields = ("title", "note_internal", "email")
    ordering = ("-start_at",)
    actions = ["approve_reservations", "reject_reservations",
               "approve_series_reservations", "reject_series_reservations"]
    list_per_page = 50

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        first_in_series = Reservation.objects.filter(
            series_id=OuterRef("series_id")
        ).annotate(
            is_pending=Case(
                When(status=Reservation.STATUS_PENDING, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("is_pending", "start_at").values("pk")[:1]
        
        return qs.filter(
            Q(series_id__isnull=True) | 
            Q(pk=Subquery(first_in_series))
        )

    # ── Custom list columns ──────────────────────────────────────

    @admin.display(description="회의실")
    def room_link(self, obj):
        if obj.series_id:
            url = reverse("admin:reservations_reservation_series_detail", args=[obj.series_id])
        else:
            url = reverse("admin:reservations_reservation_change", args=[obj.pk])
        return format_html('<a href="{}" style="font-weight:600">{}</a>', url, obj.room.name)

    @admin.display(description="제목")
    def title_link(self, obj):
        if obj.series_id:
            url = reverse("admin:reservations_reservation_series_detail", args=[obj.series_id])
        else:
            url = reverse("admin:reservations_reservation_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.title)

    @admin.display(description="시작", ordering="start_at")
    def start_at_local(self, obj):
        local = timezone.localtime(obj.start_at, TZ)
        return format_html(
            '<span style="white-space:nowrap">{}</span>',
            local.strftime("%Y-%m-%d %H:%M"),
        )

    @admin.display(description="종료", ordering="end_at")
    def end_at_local(self, obj):
        local = timezone.localtime(obj.end_at, TZ)
        return format_html(
            '<span style="white-space:nowrap">{}</span>',
            local.strftime("%Y-%m-%d %H:%M"),
        )

    @admin.display(description="상태")
    def status_badge(self, obj):
        colors = {
            Reservation.STATUS_CONFIRMED: ("#16a34a", "#dcfce7", "확정"),
            Reservation.STATUS_PENDING: ("#d97706", "#fef3c7", "대기"),
            Reservation.STATUS_CANCELLED: ("#dc2626", "#fee2e2", "취소"),
        }
        fg, bg, label = colors.get(obj.status, ("#666", "#eee", obj.status))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;'
            'font-size:12px;font-weight:600;white-space:nowrap">{}</span>',
            bg, fg, label,
        )

    @admin.display(description="시리즈")
    def series_info(self, obj):
        if not obj.series_id:
            return format_html(
                '<span style="color:#9ca3af;font-size:12px">단건</span>'
            )
        # Count siblings in the same series
        count = Reservation.objects.filter(
            series_id=obj.series_id,
            status__in=[Reservation.STATUS_CONFIRMED, Reservation.STATUS_PENDING],
        ).count()
        detail_url = reverse("admin:reservations_reservation_series_detail", args=[obj.series_id])
        return format_html(
            '<a href="{}" style="background:#ede9fe;color:#7c3aed;padding:3px 10px;'
            'border-radius:12px;font-size:12px;font-weight:600;text-decoration:none">'
            '🔁 {}건</a>',
            detail_url, count,
        )

    @admin.display(description="승인")
    def approve_button(self, obj):
        if obj.status == Reservation.STATUS_PENDING:
            if obj.series_id:
                series_url = reverse("admin:reservations_reservation_approve_series", args=[obj.series_id])
                return format_html(
                    '<a class="button" href="{}" style="font-size:12px;padding:4px 10px;'
                    'background:#7c3aed;color:#fff;border-radius:6px;text-decoration:none">'
                    '시리즈 승인</a>',
                    series_url,
                )
            single_url = reverse("admin:reservations_reservation_approve", args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="font-size:12px;padding:4px 10px;'
                'background:#16a34a;color:#fff;border-radius:6px;text-decoration:none">'
                '승인</a>',
                single_url,
            )
        return format_html('<span style="color:#9ca3af">-</span>')

    # ── Custom URLs ──────────────────────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "series/<path:series_id>/approve/",
                self.admin_site.admin_view(self.approve_series_view),
                name="reservations_reservation_approve_series",
            ),
            path(
                "series/<path:series_id>/reject/",
                self.admin_site.admin_view(self.reject_series_view),
                name="reservations_reservation_reject_series",
            ),
            path(
                "series/<path:series_id>/detail/",
                self.admin_site.admin_view(self.series_detail_view),
                name="reservations_reservation_series_detail",
            ),
            path(
                "<path:object_id>/approve/",
                self.admin_site.admin_view(self.approve_view),
                name="reservations_reservation_approve",
            ),
        ]
        return custom_urls + urls

    # ── Single approve ───────────────────────────────────────────

    def approve_view(self, request, object_id):
        reservation = self.get_object(request, object_id)
        if reservation is None:
            raise Http404("Reservation not found.")
        if not self.has_change_permission(request, obj=reservation):
            raise PermissionDenied

        if reservation.status == Reservation.STATUS_PENDING:
            reservation.status = Reservation.STATUS_CONFIRMED
            reservation.save(update_fields=["status", "updated_at"])
            send_reservation_status_email(reservation, 'confirmed')
            self.message_user(request, f"예약 #{reservation.id}을(를) 승인했습니다.")
        else:
            self.message_user(request, "이 예약은 이미 승인되었거나 취소된 상태입니다.", level=messages.WARNING)

        redirect_url = request.GET.get("next") or reverse("admin:reservations_reservation_changelist")
        return HttpResponseRedirect(redirect_url)

    # ── Series approve ───────────────────────────────────────────

    def approve_series_view(self, request, series_id):
        qs = Reservation.objects.filter(series_id=series_id, status=Reservation.STATUS_PENDING)
        count = 0
        for r in qs:
            r.status = Reservation.STATUS_CONFIRMED
            r.save(update_fields=["status", "updated_at"])
            send_reservation_status_email(r, 'confirmed')
            count += 1

        if count:
            self.message_user(request, f"시리즈 전체 {count}건을 승인했습니다.", level=messages.SUCCESS)
        else:
            self.message_user(request, "승인 대기 중인 예약이 없습니다.", level=messages.WARNING)

        redirect_url = request.GET.get("next") or reverse("admin:reservations_reservation_changelist")
        return HttpResponseRedirect(redirect_url)

    # ── Series reject ────────────────────────────────────────────

    def reject_series_view(self, request, series_id):
        qs = Reservation.objects.filter(
            series_id=series_id,
            status__in=[Reservation.STATUS_CONFIRMED, Reservation.STATUS_PENDING],
        )
        count = 0
        for r in qs:
            r.status = Reservation.STATUS_CANCELLED
            r.save(update_fields=["status", "updated_at"])
            send_reservation_status_email(r, 'cancelled')
            count += 1

        if count:
            self.message_user(request, f"시리즈 전체 {count}건을 거절/취소했습니다.", level=messages.SUCCESS)
        else:
            self.message_user(request, "처리할 예약이 없습니다.", level=messages.WARNING)

        redirect_url = request.GET.get("next") or reverse("admin:reservations_reservation_changelist")
        return HttpResponseRedirect(redirect_url)

    # ── Series detail page ───────────────────────────────────────

    def series_detail_view(self, request, series_id):
        items = list(
            Reservation.objects.filter(series_id=series_id)
            .select_related("room")
            .order_by("start_at")
        )
        if not items:
            raise Http404("Series not found.")

        pending_count = sum(1 for i in items if i.status == Reservation.STATUS_PENDING)
        confirmed_count = sum(1 for i in items if i.status == Reservation.STATUS_CONFIRMED)
        cancelled_count = sum(1 for i in items if i.status == Reservation.STATUS_CANCELLED)

        # Localize times for display
        for item in items:
            item.start_local = timezone.localtime(item.start_at, TZ).strftime("%Y-%m-%d %H:%M")
            item.end_local = timezone.localtime(item.end_at, TZ).strftime("%H:%M")

        approve_url = reverse("admin:reservations_reservation_approve_series", args=[series_id])
        reject_url = reverse("admin:reservations_reservation_reject_series", args=[series_id])
        changelist_url = reverse("admin:reservations_reservation_changelist")

        context = {
            **self.admin_site.each_context(request),
            "title": f"반복 예약 시리즈 상세",
            "items": items,
            "series_id": str(series_id),
            "room_name": items[0].room.name if items else "",
            "series_title": items[0].title if items else "",
            "total_count": len(items),
            "pending_count": pending_count,
            "confirmed_count": confirmed_count,
            "cancelled_count": cancelled_count,
            "approve_url": approve_url,
            "reject_url": reject_url,
            "changelist_url": changelist_url,
        }
        return TemplateResponse(request, "admin/reservations/series_detail.html", context)

    # ── Bulk actions ─────────────────────────────────────────────

    @admin.action(description="선택한 예약을 승인(Confirmed) 처리합니다")
    def approve_reservations(self, request, queryset):
        pending_qs = queryset.filter(status=Reservation.STATUS_PENDING)
        updated = 0
        for r in pending_qs:
            r.status = Reservation.STATUS_CONFIRMED
            r.save(update_fields=["status", "updated_at"])
            updated += 1
            send_reservation_status_email(r, 'confirmed')
        self.message_user(request, f"{updated}개의 예약을 승인했습니다.")

    @admin.action(description="선택한 예약을 거절/취소(Cancelled) 처리합니다")
    def reject_reservations(self, request, queryset):
        active_qs = queryset.filter(status__in=[Reservation.STATUS_CONFIRMED, Reservation.STATUS_PENDING])
        updated = 0
        for r in active_qs:
            r.status = Reservation.STATUS_CANCELLED
            r.save(update_fields=["status", "updated_at"])
            updated += 1
            send_reservation_status_email(r, 'cancelled')
        self.message_user(request, f"{updated}개의 예약을 거절/취소 처리했습니다.")

    @admin.action(description="선택한 예약의 시리즈 전체를 승인합니다")
    def approve_series_reservations(self, request, queryset):
        series_ids = set(
            queryset.filter(series_id__isnull=False)
            .values_list("series_id", flat=True)
        )
        if not series_ids:
            self.message_user(request, "선택된 항목 중 시리즈 예약이 없습니다.", level=messages.WARNING)
            return
        updated = 0
        for r in Reservation.objects.filter(series_id__in=series_ids, status=Reservation.STATUS_PENDING):
            r.status = Reservation.STATUS_CONFIRMED
            r.save(update_fields=["status", "updated_at"])
            send_reservation_status_email(r, 'confirmed')
            updated += 1
        self.message_user(
            request,
            f"{len(series_ids)}개 시리즈, 총 {updated}건을 승인했습니다.",
        )

    @admin.action(description="선택한 예약의 시리즈 전체를 거절/취소합니다")
    def reject_series_reservations(self, request, queryset):
        series_ids = set(
            queryset.filter(series_id__isnull=False)
            .values_list("series_id", flat=True)
        )
        if not series_ids:
            self.message_user(request, "선택된 항목 중 시리즈 예약이 없습니다.", level=messages.WARNING)
            return
        updated = 0
        for r in Reservation.objects.filter(
            series_id__in=series_ids,
            status__in=[Reservation.STATUS_CONFIRMED, Reservation.STATUS_PENDING],
        ):
            r.status = Reservation.STATUS_CANCELLED
            r.save(update_fields=["status", "updated_at"])
            send_reservation_status_email(r, 'cancelled')
            updated += 1
        self.message_user(
            request,
            f"{len(series_ids)}개 시리즈, 총 {updated}건을 거절/취소했습니다.",
        )

    # ── save_model / delete overrides ────────────────────────────

    def save_model(self, request, obj, form, change):
        if change:
            orig = Reservation.objects.get(pk=obj.pk)
            super().save_model(request, obj, form, change)

            # 1. Cancelled
            if orig.status != Reservation.STATUS_CANCELLED and obj.status == Reservation.STATUS_CANCELLED:
                send_reservation_status_email(obj, 'cancelled')
            # 2. Confirmed (Pending -> Confirmed)
            elif orig.status == Reservation.STATUS_PENDING and obj.status == Reservation.STATUS_CONFIRMED:
                send_reservation_status_email(obj, 'confirmed')
            # 3. Modified (time, room, title changed, but not currently cancelled)
            elif obj.status != Reservation.STATUS_CANCELLED and (
                orig.room != obj.room or
                orig.start_at != obj.start_at or
                orig.end_at != obj.end_at or
                orig.title != obj.title
            ):
                send_reservation_status_email(obj, 'modified')
        else:
            super().save_model(request, obj, form, change)
            if obj.status == Reservation.STATUS_CONFIRMED:
                send_reservation_status_email(obj, 'confirmed')

    def delete_model(self, request, obj):
        send_reservation_status_email(obj, 'cancelled')
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            send_reservation_status_email(obj, 'cancelled')
        super().delete_queryset(request, queryset)


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("room", "start_at", "end_at", "reason")
    list_filter = ("room",)


@admin.register(AccessDevice)
class AccessDeviceAdmin(admin.ModelAdmin):
    list_display = ("label", "enabled", "created_at")
    list_editable = ("enabled",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("at", "actor_type", "actor_label", "action", "ip")
    list_filter = ("actor_type", "action")
    search_fields = ("actor_label",)


