import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from vehicles.models import DealerVehicleReel
from vehicles.serializers import ReelNewsfeedSerializer
from django.contrib.auth import get_user_model
import json
User = get_user_model()
class DummyRequest:
    def __init__(self, user):
        self.user = user
    def build_absolute_uri(self, url):
        return url

user = User.objects.first()
queryset = DealerVehicleReel.objects.filter(
    vehicle__is_draft=False,
    dealer__business_info__verification_status='verified'
).distinct()

serializer = ReelNewsfeedSerializer(queryset, many=True, context={'request': DummyRequest(user)})
for item in serializer.data:
    print(f"ID: {item.get('id')}, Comments Count: {item.get('comments_count')}")
