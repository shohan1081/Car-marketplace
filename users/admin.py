from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import User, OTP, UserPreference, BusinessInformation

REJECTABLE_FIELDS = (
    ("dealership_name", "Dealership Name"),
    ("display_name", "Display Name"),
    ("specialization", "Specialization"),
    ("street_address", "Street Address"),
    ("state", "State"),
    ("division", "Division"),
    ("business_website", "Business Website"),
    ("trade_license_number", "Trade License Number"),
    ("dealership_logo", "Dealership Logo"),
    ("cover_image", "Cover Image"),
    ("dealership_description", "Dealership Description"),
    ("operating_hours", "Operating Hours"),
    ("facebook_url", "Facebook URL"),
    ("instagram_url", "Instagram URL"),
    ("dealership_license_document", "Dealership License Document"),
    ("dealership_license_number", "Dealership License Number"),
    ("expiry_date", "Expiry Date"),
)

class BusinessInformationAdminForm(forms.ModelForm):
    rejected_fields = forms.MultipleChoiceField(
        choices=REJECTABLE_FIELDS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select the fields that need to be corrected by the dealer."
    )

    class Meta:
        model = BusinessInformation
        fields = '__all__'

class BusinessInformationAdmin(ModelAdmin):
    form = BusinessInformationAdminForm
    list_display = ['dealership_name', 'user', 'verification_status', 'rejection_reason']
    list_filter = ['verification_status']
    search_fields = ['dealership_name', 'user__email']
    fields = [
        'user', 'verification_status', 'rejection_reason', 'rejected_fields',
        'dealership_name', 'display_name', 'specialization',
        'street_address', 'state', 'division',
        'latitude', 'longitude', 'business_website',
        'trade_license_number', 'dealership_license_document',
        'dealership_license_number', 'expiry_date',
        'dealership_logo', 'cover_image', 'dealership_description',
        'operating_hours', 'facebook_url', 'instagram_url'
    ]
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
