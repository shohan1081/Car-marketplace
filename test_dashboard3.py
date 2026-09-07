import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from rest_framework.test import APIRequestFactory, force_authenticate
from vehicles.views import DealerDashboardView
from django.contrib.auth import get_user_model
import json

User = get_user_model()
user = User.objects.filter(is_dealer=True).first()
factory = APIRequestFactory()
request = factory.get('/api/vehicles/dashboard/')
force_authenticate(request, user=user)

view = DealerDashboardView.as_view()
response = view(request)
print(json.dumps(response.data, indent=2))
