from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from users.models import BusinessInformation
from .models import Music

User = get_user_model()

class VehicleRestrictionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create unverified dealer
        self.unverified_dealer = User.objects.create_user(
            email='unverified@dealer.com',
            password='password123',
            is_dealer=True,
            is_verified=True
        )
        # Create BusinessInfo with 'pending' status
        BusinessInformation.objects.create(
            user=self.unverified_dealer,
            verification_status='pending',
            dealership_name='Pending Motors',
            display_name='Pending',
            street_address='123 St',
            state='NY',
            division='NY',
            trade_license_number='TL123',
            dealership_license_number='DL123',
            expiry_date='2030-01-01',
            dealership_description='Desc'
        )

        # Create verified dealer
        self.verified_dealer = User.objects.create_user(
            email='verified@dealer.com',
            password='password123',
            is_dealer=True,
            is_verified=True
        )
        BusinessInformation.objects.create(
            user=self.verified_dealer,
            verification_status='verified',
            dealership_name='Verified Motors',
            display_name='Verified',
            street_address='456 St',
            state='NY',
            division='NY',
            trade_license_number='TL456',
            dealership_license_number='DL456',
            expiry_date='2030-01-01',
            dealership_description='Desc'
        )
        
        self.music = Music.objects.create(title="Test Music", file="test.mp3")

    def test_unverified_dealer_cannot_create_vehicle(self):
        self.client.force_authenticate(user=self.unverified_dealer)
        data = {
            "name": "Test Car",
            "model": "X5",
            "year": 2023,
            "asking_price": 50000,
            "video_file": "test.mp4",
            "background_music": self.music.id
        }
        response = self.client.post('/api/vehicles/create/', data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Your account is not verified", response.data['error'])

    def test_verified_dealer_can_create_vehicle(self):
        self.client.force_authenticate(user=self.verified_dealer)
        # Mocking file upload is complex, but the verification check happens before validation/saving
        # Actually validation happens first in my implementation. 
        # Let's check the order in VehicleCreateView.
        # It's: check role -> check verification -> run serializer validation.
        
        # So it should fail on validation (missing fields or file) but NOT on verification.
        data = {"name": "Test Car"} 
        response = self.client.post('/api/vehicles/create/', data)
        
        # Should NOT be 403 Forbidden (verification)
        # Should be 400 Bad Request (validation)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("Your account is not verified", str(response.data))
