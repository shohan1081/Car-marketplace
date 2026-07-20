import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.test import RequestFactory
from vehicles.views import DealerDashboardView
from django.contrib.auth import get_user_model
import json

User = get_user_model()
user = User.objects.first()
factory = RequestFactory()
request = factory.get('/api/vehicles/dashboard/')
request.user = user

view = DealerDashboardView.as_view()
response = view(request)
print(json.dumps(response.data, indent=2))
