from django.db import models
from django.conf import settings

class SubscriptionPackage(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=30)
    
    # Store-specific product IDs
    apple_product_id = models.CharField(max_length=255, unique=True)
    google_product_id = models.CharField(max_length=255, unique=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class DealerSubscription(models.Model):
    PLATFORM_CHOICES = [
        ('apple', 'Apple App Store'),
        ('google', 'Google Play Store'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('canceled', 'Canceled'), # Still active until period ends
        ('expired', 'Expired'),
        ('past_due', 'Past Due'),
        ('grace_period', 'Grace Period'),
    ]

    dealer = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    package = models.ForeignKey(SubscriptionPackage, on_delete=models.SET_NULL, null=True)
    
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # This ID links all renewals and updates for a single subscription stream
    original_transaction_id = models.CharField(max_length=255, unique=True)
    
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    
    auto_renew = models.BooleanField(default=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.dealer.email} - {self.package.name if self.package else 'No Package'}"

    @property
    def is_valid(self):
        from django.utils import timezone
        return self.status in ['active', 'canceled', 'grace_period'] and self.current_period_end > timezone.now()

class SubscriptionTransaction(models.Model):
    subscription = models.ForeignKey(DealerSubscription, on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
    dealer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    transaction_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=100) # e.g., 'INITIAL_PURCHASE', 'RENEWAL', 'WEBHOOK_UPDATE'
    
    raw_payload = models.JSONField()
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.event_type}"
