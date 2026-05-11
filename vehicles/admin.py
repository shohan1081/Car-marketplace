from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Music, Vehicle, DealerVehicleReel

@admin.register(Music)
class MusicAdmin(ModelAdmin):
    list_display = ['title', 'created_at']
    search_fields = ['title']

@admin.register(Vehicle)
class VehicleAdmin(ModelAdmin):
    list_display = ['name', 'model', 'year', 'dealer', 'is_draft']
    list_filter = ['is_draft', 'body_type', 'condition', 'fuel_type']
    search_fields = ['name', 'model', 'dealer__email']

@admin.register(DealerVehicleReel)
class DealerVehicleReelAdmin(ModelAdmin):
    list_display = ['vehicle', 'dealer', 'created_at']
