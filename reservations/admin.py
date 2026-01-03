from django.contrib import admin
from .models import Room, Reservation, Block, AccessDevice, AuditLog


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order", "location", "active")
    list_editable = ("sort_order", "active")
    search_fields = ("name", "location")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("room", "start_at", "end_at", "title", "status")
    list_filter = ("status", "room")
    search_fields = ("title", "note_internal")
    ordering = ("-start_at",)


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

