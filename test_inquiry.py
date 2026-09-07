import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from vehicles.models import Inquiry
from vehicles.serializers import InquirySerializer
qs = Inquiry.objects.all()
if qs.exists():
    print(InquirySerializer(qs.first()).data)
