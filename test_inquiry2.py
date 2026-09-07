import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from vehicles.models import VehicleInquiry
from vehicles.serializers import VehicleInquirySerializer
from django.contrib.auth import get_user_model
import json

qs = VehicleInquiry.objects.all()
if qs.exists():
    print(json.dumps(VehicleInquirySerializer(qs.first()).data, indent=2))
else:
    print("No inquiries found")
