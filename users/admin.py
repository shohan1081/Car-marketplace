from django.contrib import admin
from .models import User, OTP, UserPreference, BusinessInformation

admin.site.register(User)
admin.site.register(OTP)
admin.site.register(UserPreference)
admin.site.register(BusinessInformation)
