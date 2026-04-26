from django.contrib import admin
from .models import Room, Reservation, Block, AccessDevice, AuditLog


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order", "location", "active", "requires_approval")
    list_editable = ("sort_order", "active", "requires_approval")
    search_fields = ("name", "location")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("room", "start_at", "end_at", "title", "status")
    list_filter = ("status", "room")
    search_fields = ("title", "note_internal")
    ordering = ("-start_at",)
    actions = ["approve_reservations", "reject_reservations"]

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

