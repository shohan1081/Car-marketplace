from rest_framework import serializers
from .models import SubscriptionPackage, DealerSubscription, SubscriptionTransaction

class SubscriptionPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPackage
        fields = '__all__'

class DealerSubscriptionSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source='package.name', read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = DealerSubscription
        fields = [
            'package_name', 'platform', 'status', 'current_period_end', 
            'auto_renew', 'is_valid', 'original_transaction_id'
        ]
