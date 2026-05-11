from django.contrib import admin
from .models import User, OTP, UserPreference, BusinessInformation

class BusinessInformationAdmin(admin.ModelAdmin):
    list_display = ['dealership_name', 'user', 'verification_status']
    list_filter = ['verification_status']
    search_fields = ['dealership_name', 'user__email']
    actions = ['verify_dealers', 'reject_dealers']

    def verify_dealers(self, request, queryset):
        queryset.update(verification_status='verified', rejection_reason=None)
        for info in queryset:
            user = info.user
            user.is_verified = True # Assuming overall verification depends on business info for dealers
            user.save()
    verify_dealers.short_description = "Mark selected dealers as Verified"

    def reject_dealers(self, request, queryset):
        # In a real scenario, you'd want a form to provide the reason
        queryset.update(verification_status='rejected')
    reject_dealers.short_description = "Mark selected dealers as Rejected"

admin.site.register(User)
admin.site.register(OTP)
admin.site.register(UserPreference)
admin.site.register(BusinessInformation, BusinessInformationAdmin)
