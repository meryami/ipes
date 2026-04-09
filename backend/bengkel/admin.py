from django.contrib import admin
from .models import Bengkel, Jemputan, Kehadiran


@admin.register(Bengkel)
class BengkelAdmin(admin.ModelAdmin):
    list_display  = ["title", "tarikh", "lokasi_nama", "jumlah_jemputan", "created_at"]
    list_filter   = ["tarikh"]
    search_fields = ["title", "organizer_nama"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Jemputan)
class JemputanAdmin(admin.ModelAdmin):
    list_display  = ["nama", "email", "organisasi", "bengkel", "status", "created_at"]
    list_filter   = ["status", "bengkel"]
    search_fields = ["nama", "email", "organisasi"]
    readonly_fields = ["token", "qr_token", "created_at"]


@admin.register(Kehadiran)
class KehadiranAdmin(admin.ModelAdmin):
    list_display  = ["jemputan", "checked_in_at", "checked_in_by"]
    readonly_fields = ["checked_in_at"]
