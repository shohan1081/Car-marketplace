import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from vehicles.models import VehicleInquiry
from vehicles.serializers import VehicleInquirySerializer
qs = VehicleInquiry.objects.all()
if qs.exists():
    print(VehicleInquirySerializer(qs.first()).data)
else:
    print("No inquiries found")
