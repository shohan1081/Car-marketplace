from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import User, OTP, UserPreference, BusinessInformation

class BusinessInformationAdmin(ModelAdmin):
    list_display = ['dealership_name', 'user', 'verification_status']
    list_filter = ['verification_status']
    search_fields = ['dealership_name', 'user__email']
    actions = ['verify_dealers', 'reject_dealers']

    def verify_dealers(self, request, queryset):
        queryset.update(verification_status='verified', rejection_reason=None)
        for info in queryset:
            user = info.user
            user.is_verified = True
            user.save()
    verify_dealers.short_description = "Mark selected dealers as Verified"

    def reject_dealers(self, request, queryset):
        queryset.update(verification_status='rejected')
    reject_dealers.short_description = "Mark selected dealers as Rejected"

@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ['email', 'full_name', 'is_buyer', 'is_dealer', 'is_verified']
    search_fields = ['email', 'full_name']
    list_filter = ['is_buyer', 'is_dealer', 'is_verified']

@admin.register(OTP)
class OTPAdmin(ModelAdmin):
    list_display = ['user', 'code', 'created_at', 'is_used']

@admin.register(UserPreference)
class UserPreferenceAdmin(ModelAdmin):
    list_display = ['user', 'city']

admin.site.register(BusinessInformation, BusinessInformationAdmin)
