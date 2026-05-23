from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import SubscriptionPackage, DealerSubscription, SubscriptionTransaction

@admin.register(SubscriptionPackage)
class SubscriptionPackageAdmin(ModelAdmin):
    list_display = ['name', 'price', 'duration_days', 'is_active']

@admin.register(DealerSubscription)
class DealerSubscriptionAdmin(ModelAdmin):
    list_display = ['dealer', 'package', 'status', 'platform', 'current_period_end', 'is_valid_display']
    list_filter = ['status', 'platform', 'package']
    search_fields = ['dealer__email', 'original_transaction_id']

    def is_valid_display(self, obj):
        return obj.is_valid
    is_valid_display.boolean = True
    is_valid_display.short_description = "Is Valid"

@admin.register(SubscriptionTransaction)
class SubscriptionTransactionAdmin(ModelAdmin):
    list_display = ['dealer', 'transaction_id', 'event_type', 'processed_at']
    list_filter = ['event_type']
    search_fields = ['dealer__email', 'transaction_id']
    readonly_fields = ['raw_payload']
