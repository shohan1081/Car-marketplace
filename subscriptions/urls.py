from django.urls import path
from .views import (
    SubscriptionPackageListView, VerifyPurchaseView, 
    AppleWebhookView, GoogleWebhookView, RevenueCatWebhookView
)

urlpatterns = [
    path('packages/', SubscriptionPackageListView.as_view(), name='package-list'),
    path('verify/', VerifyPurchaseView.as_view(), name='verify-purchase'),
    path('webhook/apple/', AppleWebhookView.as_view(), name='apple-webhook'),
    path('webhook/google/', GoogleWebhookView.as_view(), name='google-webhook'),
    path('webhook/revenuecat/', RevenueCatWebhookView.as_view(), name='revenuecat-webhook'),
]
