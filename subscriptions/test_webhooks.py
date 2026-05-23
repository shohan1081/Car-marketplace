import base64
import json
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from subscriptions.models import SubscriptionPackage, DealerSubscription, SubscriptionTransaction
from unittest.mock import patch

User = get_user_model()

class WebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="dealer@example.com", password="password", is_dealer=True)
        self.package = SubscriptionPackage.objects.create(
            name="Premium",
            price=99.99,
            apple_product_id="apple_premium",
            google_product_id="google_premium"
        )
        self.subscription = DealerSubscription.objects.create(
            dealer=self.user,
            package=self.package,
            platform='apple',
            status='active',
            original_transaction_id="orig_123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30)
        )

    @patch('subscriptions.views.process_apple_notification')
    def test_apple_webhook_renewal(self, mock_process):
        # Mocking Apple V2 Notification
        mock_process.return_value = {
            'notificationType': 'DID_RENEW',
            'data': {
                'transaction_info': {
                    'originalTransactionId': 'orig_123',
                    'transactionId': 'new_123',
                    'expiresDate': (timezone.now() + timezone.timedelta(days=60)).timestamp() * 1000
                }
            }
        }
        
        response = self.client.post('/api/subscriptions/webhook/apple/', {'signedPayload': 'dummy'}, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, 'active')
        self.assertTrue(self.subscription.current_period_end > timezone.now() + timezone.timedelta(days=50))
        
        # Check transaction log
        self.assertTrue(SubscriptionTransaction.objects.filter(event_type='APPLE_DID_RENEW').exists())

    @patch('subscriptions.views.process_google_notification')
    @patch('subscriptions.views.verify_google_purchase')
    def test_google_webhook_cancel(self, mock_verify, mock_process):
        # Mocking Google RTDN
        mock_process.return_value = {
            'subscriptionNotification': {
                'purchaseToken': 'orig_123',
                'notificationType': 3 # CANCELED
            }
        }
        mock_verify.return_value = {
            'expiryTimeMillis': (timezone.now() + timezone.timedelta(days=10)).timestamp() * 1000,
            'autoRenewing': False
        }
        
        # Update sub to google
        self.subscription.platform = 'google'
        self.subscription.save()

        # Google Webhook usually comes with a base64 'data' inside 'message'
        payload = {
            'message': {
                'data': base64.b64encode(b'{"dummy": true}').decode('utf-8')
            }
        }
        
        response = self.client.post('/api/subscriptions/webhook/google/', payload, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, 'canceled')
        self.assertFalse(self.subscription.auto_renew)
