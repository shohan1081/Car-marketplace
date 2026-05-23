import json
import base64
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from appstoreserverlibrary.api_client import AppStoreServerAPIClient
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
import jwt # PyJWT is in requirements.txt

# Google Play Verification
def verify_google_purchase(package_name, subscription_id, token):
    if not settings.GOOGLE_SERVICE_ACCOUNT_JSON:
        return None
        
    scopes = ['https://www.googleapis.com/auth/androidpublisher']
    credentials = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=scopes
    )
    
    service = build('androidpublisher', 'v3', credentials=credentials)
    try:
        purchase = service.purchases().subscriptions().get(
            packageName=package_name,
            subscriptionId=subscription_id,
            token=token
        ).execute()
        return purchase
    except Exception as e:
        print(f"Google Purchase Verification Error: {e}")
        return None

# Apple App Store Verification & Client
def get_apple_client():
    if not all([settings.APPLE_PRIVATE_KEY, settings.APPLE_KEY_ID, settings.APPLE_ISSUER_ID]):
        return None
        
    env = Environment.SANDBOX if settings.APPLE_ENVIRONMENT == 'sandbox' else Environment.PRODUCTION
    return AppStoreServerAPIClient(
        settings.APPLE_PRIVATE_KEY,
        settings.APPLE_KEY_ID,
        settings.APPLE_ISSUER_ID,
        settings.APPLE_BUNDLE_ID,
        env
    )

def decode_apple_jws(signed_payload):
    """
    Decodes an Apple JWS without signature verification. 
    In production, you should use SignedDataVerifier with Apple Root Certificates.
    """
    try:
        # Apple JWS components are Base64URL encoded
        return jwt.decode(signed_payload, options={"verify_signature": False})
    except Exception as e:
        print(f"Error decoding Apple JWS: {e}")
        return None

def process_apple_notification(signed_payload):
    """
    Decodes the full Apple V2 notification payload.
    """
    decoded_payload = decode_apple_jws(signed_payload)
    if not decoded_payload:
        return None
        
    data = decoded_payload.get('data', {})
    
    # Also decode the signed transaction info inside data
    signed_transaction_info = data.get('signedTransactionInfo')
    if signed_transaction_info:
        data['transaction_info'] = decode_apple_jws(signed_transaction_info)
        
    signed_renewal_info = data.get('signedRenewalInfo')
    if signed_renewal_info:
        data['renewal_info'] = decode_apple_jws(signed_renewal_info)
        
    decoded_payload['data'] = data
    return decoded_payload

def process_google_notification(message_data_b64):
    """
    Decodes the Google RTDN data from base64.
    """
    try:
        decoded_bytes = base64.b64decode(message_data_b64)
        return json.loads(decoded_bytes)
    except Exception as e:
        print(f"Error decoding Google notification: {e}")
        return None
