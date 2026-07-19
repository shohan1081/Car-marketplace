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

    def clean(self):
        cleaned_data = super().clean()
        rejected_fields = cleaned_data.get('rejected_fields')
        rejection_reason = cleaned_data.get('rejection_reason')
        verification_status = cleaned_data.get('verification_status')

        # Automatically change status to rejected if admin filled out rejection details
        if (rejected_fields or rejection_reason) and verification_status == 'pending':
            cleaned_data['verification_status'] = 'rejected'

        # Automatically clear rejection details if status is changed to verified
        if verification_status == 'verified':
            cleaned_data['rejection_reason'] = None
            cleaned_data['rejected_fields'] = []

        return cleaned_data

class BusinessInformationAdmin(ModelAdmin):
    form = BusinessInformationAdminForm
    list_display = ['dealership_name', 'user', 'verification_status', 'rejection_reason']
    list_filter = ['verification_status']
    search_fields = ['dealership_name', 'user__email']
    def get_fieldsets(self, request, obj=None):
        hide_rejection = obj and obj.verification_status == 'verified'
        
        status_fields = ('user', 'verification_status')
        fieldsets = [('Status', {'fields': status_fields})]
        
        if not hide_rejection:
            fieldsets.append(('Rejection Details', {
                'fields': ('rejection_reason', 'rejected_fields'),
                'classes': ('collapse',),
            }))
            
        fieldsets.extend([
            ('Basic Information', {'fields': ('dealership_name', 'display_name', 'specialization', 'dealership_description')}),
            ('Location & Contact', {'fields': ('street_address', 'state', 'division', 'latitude', 'longitude', 'business_website', 'facebook_url', 'instagram_url')}),
            ('License & Verification', {'fields': ('trade_license_number', 'dealership_license_document', 'dealership_license_number', 'expiry_date')}),
            ('Media & Hours', {'fields': ('dealership_logo', 'cover_image', 'operating_hours')}),
        ])
        return tuple(fieldsets)
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

from unfold.admin import StackedInline

class BusinessInformationInline(StackedInline):
    model = BusinessInformation
    form = BusinessInformationAdminForm
    can_delete = False
    verbose_name_plural = 'Business Information'

    def get_fieldsets(self, request, obj=None):
        hide_rejection = False
        if obj:
            try:
                if obj.business_info.verification_status == 'verified':
                    hide_rejection = True
            except Exception:
                pass

        fieldsets = [('Status', {'fields': ('verification_status',)})]
        
        if not hide_rejection:
            fieldsets.append(('Rejection Details', {
                'fields': ('rejection_reason', 'rejected_fields'),
                'classes': ('collapse',),
            }))
            
        fieldsets.extend([
            ('Basic Information', {'fields': ('dealership_name', 'display_name', 'specialization', 'dealership_description')}),
            ('Location & Contact', {'fields': ('street_address', 'state', 'division', 'latitude', 'longitude', 'business_website', 'facebook_url', 'instagram_url')}),
            ('License & Verification', {'fields': ('trade_license_number', 'dealership_license_document', 'dealership_license_number', 'expiry_date')}),
            ('Media & Hours', {'fields': ('dealership_logo', 'cover_image', 'operating_hours')}),
        ])
        return tuple(fieldsets)

@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ['email', 'full_name', 'is_buyer', 'is_dealer', 'is_verified']
    search_fields = ['email', 'full_name']
    list_filter = ['is_buyer', 'is_dealer', 'is_verified']
    inlines = [BusinessInformationInline]
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'phone_number', 'designation', 'profile_photo', 'location')}),
        ('Roles & Status', {'fields': ('is_buyer', 'is_dealer', 'is_verified', 'is_active')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

@admin.register(OTP)
class OTPAdmin(ModelAdmin):
    list_display = ['user', 'code', 'created_at', 'is_used']

@admin.register(UserPreference)
class UserPreferenceAdmin(ModelAdmin):
    list_display = ['user', 'city']

admin.site.register(BusinessInformation, BusinessInformationAdmin)

