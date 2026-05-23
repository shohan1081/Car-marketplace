import json
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import SubscriptionPackage, DealerSubscription, SubscriptionTransaction
from .serializers import SubscriptionPackageSerializer, DealerSubscriptionSerializer
from .utils import (
    verify_google_purchase, get_apple_client, 
    process_apple_notification, process_google_notification
)

User = get_user_model()

class SubscriptionPackageListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        packages = SubscriptionPackage.objects.filter(is_active=True)
        serializer = SubscriptionPackageSerializer(packages, many=True)
        return Response(serializer.data)

class VerifyPurchaseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can subscribe."}, status=status.HTTP_403_FORBIDDEN)
            
        if not request.user.is_verified:
            return Response({"error": "Please get your account verified before subscribing."}, status=status.HTTP_403_FORBIDDEN)

        platform = request.data.get('platform') # 'apple' or 'google'
        token = request.data.get('token') # Google purchase token or Apple transactionId
        product_id = request.data.get('product_id')

        try:
            package = SubscriptionPackage.objects.get(
                apple_product_id=product_id if platform == 'apple' else '',
                google_product_id=product_id if platform == 'google' else ''
            )
        except SubscriptionPackage.DoesNotExist:
            return Response({"error": "Invalid product ID."}, status=status.HTTP_400_BAD_REQUEST)

        if platform == 'google':
            purchase = verify_google_purchase(settings.GOOGLE_PLAY_PACKAGE_NAME, product_id, token)
            if not purchase:
                return Response({"error": "Google verification failed."}, status=status.HTTP_400_BAD_REQUEST)
            
            expiry_time_ms = int(purchase.get('expiryTimeMillis'))
            expiry_date = timezone.make_aware(datetime.fromtimestamp(expiry_time_ms / 1000.0))
            
            sub, created = DealerSubscription.objects.update_or_create(
                dealer=request.user,
                defaults={
                    'package': package,
                    'platform': 'google',
                    'status': 'active',
                    'original_transaction_id': token,
                    'current_period_start': timezone.now(),
                    'current_period_end': expiry_date,
                    'auto_renew': purchase.get('autoRenewing', True)
                }
            )
            
            SubscriptionTransaction.objects.create(
                subscription=sub,
                dealer=request.user,
                transaction_id=token,
                event_type='INITIAL_PURCHASE_GOOGLE',
                raw_payload=purchase
            )
            
            return Response(DealerSubscriptionSerializer(sub).data)

        elif platform == 'apple':
            client = get_apple_client()
            if not client:
                 return Response({"error": "Apple client not configured."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            try:
                response = client.get_transaction_info(token)
                signed_info = response.signedTransactionInfo
                from .utils import decode_apple_jws
                info = decode_apple_jws(signed_info)
                orig_id = info.get('originalTransactionId', token)
                expires_ms = info.get('expiresDate')
                
                if expires_ms:
                    expiry_date = timezone.make_aware(datetime.fromtimestamp(expires_ms / 1000.0))
                else:
                    expiry_date = timezone.now() + timedelta(days=package.duration_days)

                sub, created = DealerSubscription.objects.update_or_create(
                    dealer=request.user,
                    defaults={
                        'package': package,
                        'platform': 'apple',
                        'status': 'active',
                        'original_transaction_id': orig_id,
                        'current_period_start': timezone.now(),
                        'current_period_end': expiry_date,
                    }
                )
                
                SubscriptionTransaction.objects.create(
                    subscription=sub,
                    dealer=request.user,
                    transaction_id=token,
                    event_type='INITIAL_PURCHASE_APPLE',
                    raw_payload=info
                )
                
                return Response(DealerSubscriptionSerializer(sub).data)
            except Exception as e:
                return Response({"error": f"Apple verification failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"error": "Unsupported platform."}, status=status.HTTP_400_BAD_REQUEST)

class RevenueCatWebhookView(APIView):
    """
    Handles unified webhooks from RevenueCat.
    RevenueCat handles Apple/Google verification and sends a single format here.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Optional: Verify RevenueCat Auth Header
        auth_header = request.headers.get('Authorization')
        expected_token = getattr(settings, 'REVENUECAT_WEBHOOK_AUTH_TOKEN', None)
        if expected_token and auth_header != f"Bearer {expected_token}":
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data
        event = payload.get('event', {})
        event_type = event.get('type')
        app_user_id = event.get('app_user_id') # This should be our User ID (string)
        product_id = event.get('product_id')
        
        # RevenueCat timestamps are in milliseconds
        expires_date_ms = event.get('expiration_at_ms')
        orig_transaction_id = event.get('original_transaction_id')
        store = event.get('store', '').lower() # 'app_store' or 'play_store'

        try:
            # We use ID because RevenueCat usually sends our internal DB ID if configured in Flutter
            user = User.objects.get(id=app_user_id)
        except (User.DoesNotExist, ValueError):
            # Fallback to email if ID match fails
            user = User.objects.filter(email=app_user_id).first()
            if not user:
                print(f"RevenueCat User not found: {app_user_id}")
                return Response({"status": "user not found"}, status=200)

        # Map RevenueCat Store to our Platform
        platform = 'apple' if store == 'app_store' else 'google'
        
        # Find Package
        package = SubscriptionPackage.objects.filter(
            apple_product_id=product_id if platform == 'apple' else '',
            google_product_id=product_id if platform == 'google' else ''
        ).first()

        # Update or Create Subscription
        defaults = {
            'package': package,
            'platform': platform,
            'original_transaction_id': orig_transaction_id,
        }
        
        if expires_date_ms:
            defaults['current_period_end'] = timezone.make_aware(datetime.fromtimestamp(expires_date_ms / 1000.0))
            defaults['current_period_start'] = timezone.now() # Approximate

        # Map RevenueCat event types to internal status
        # Event types: INITIAL_PURCHASE, RENEWAL, CANCELLATION, EXPIRATION, BILLING_ISSUE, PRODUCT_CHANGE, REVOKE
        if event_type in ['INITIAL_PURCHASE', 'RENEWAL', 'PRODUCT_CHANGE']:
            defaults['status'] = 'active'
        elif event_type == 'CANCELLATION':
            # In RevenueCat, cancellation means auto-renew is off, but access might remain until expiry
            defaults['status'] = 'canceled'
            defaults['auto_renew'] = False
        elif event_type in ['EXPIRATION', 'REVOKE']:
            defaults['status'] = 'expired'
        elif event_type == 'BILLING_ISSUE':
            defaults['status'] = 'past_due'

        subscription, created = DealerSubscription.objects.update_or_create(
            dealer=user,
            defaults=defaults
        )

        # Log Transaction
        SubscriptionTransaction.objects.create(
            subscription=subscription,
            dealer=user,
            transaction_id=event.get('transaction_id', orig_transaction_id),
            event_type=f"REVENUECAT_{event_type}",
            raw_payload=payload
        )

        return Response({"status": "processed"})

class AppleWebhookView(APIView):
    # Kept for backward compatibility or direct store usage
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        return Response({"status": "use revenuecat webhook instead"}, status=200)

class GoogleWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        return Response({"status": "use revenuecat webhook instead"}, status=200)
