from django.contrib import admin, messages
from django.http import Http404, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.core.exceptions import PermissionDenied

from .models import Room, Reservation, Block, AccessDevice, AuditLog


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order", "location", "active", "requires_approval")
    list_editable = ("sort_order", "active", "requires_approval")
    search_fields = ("name", "location")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("room", "start_at", "end_at", "title", "status", "approve_button")
    list_filter = ("status", "room")
    search_fields = ("title", "note_internal")
    ordering = ("-start_at",)
    actions = ["approve_reservations", "reject_reservations"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/approve/",
                self.admin_site.admin_view(self.approve_view),
                name="reservations_reservation_approve",
            ),
        ]
        return custom_urls + urls

    def approve_button(self, obj):
        if obj.status == Reservation.STATUS_PENDING:
            url = reverse("admin:reservations_reservation_approve", args=[obj.pk])
            return format_html(
                '<a class="button" href="{}">승인</a>',
                url,
            )
        return "-"
    approve_button.short_description = "승인"
    approve_button.allow_tags = True

    def approve_view(self, request, object_id):
        reservation = self.get_object(request, object_id)
        if reservation is None:
            raise Http404("Reservation not found.")
        if not self.has_change_permission(request, obj=reservation):
            raise PermissionDenied

        if reservation.status == Reservation.STATUS_PENDING:
            reservation.status = Reservation.STATUS_CONFIRMED
            reservation.save(update_fields=["status", "updated_at"])
            self.message_user(request, f"예약 {reservation.id}을(를) 승인했습니다.")
        else:
            self.message_user(request, "이 예약은 이미 승인되었거나 취소된 상태입니다.", level=messages.WARNING)

        redirect_url = request.GET.get("next") or reverse("admin:reservations_reservation_changelist")
        return HttpResponseRedirect(redirect_url)

    @admin.action(description="선택한 예약을 승인(Confirmed) 처리합니다")
    def approve_reservations(self, request, queryset):
        updated = queryset.update(status=Reservation.STATUS_CONFIRMED)
        self.message_user(request, f"{updated}개의 예약을 승인했습니다.")

    @admin.action(description="선택한 예약을 거절/취소(Cancelled) 처리합니다")
    def reject_reservations(self, request, queryset):
        updated = queryset.update(status=Reservation.STATUS_CANCELLED)
        self.message_user(request, f"{updated}개의 예약을 거절했습니다.")


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

