from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from users.models import BusinessInformation
from .models import Music, Vehicle, DealerVehicleReel, AIVideoGeneration

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


class AIVideoAndInventoryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = User.objects.create_user(
            email='dealer_ai@test.com',
            password='password123',
            is_dealer=True,
            is_verified=True
        )
        self.other_dealer = User.objects.create_user(
            email='dealer_other@test.com',
            password='password123',
            is_dealer=True,
            is_verified=True
        )
        self.buyer = User.objects.create_user(
            email='buyer_ai@test.com',
            password='password123',
            is_dealer=False,
            is_verified=True
        )
        # Completed unused AI video
        self.unused_gen = AIVideoGeneration.objects.create(
            dealer=self.dealer,
            prompt='Test unused',
            status='completed'
        )
        # Completed used AI video
        self.used_gen = AIVideoGeneration.objects.create(
            dealer=self.dealer,
            prompt='Test used',
            status='completed'
        )
        # Pending AI video
        self.pending_gen = AIVideoGeneration.objects.create(
            dealer=self.dealer,
            prompt='Test pending',
            status='pending'
        )
        def create_vehicle(name):
            return Vehicle.objects.create(
                dealer=self.dealer,
                name=name,
                model='Model X',
                description='Test description',
                year=2024,
                variant='Standard',
                body_type='sedan',
                condition='used',
                mileage_km=10000,
                color='White',
                fuel_type='petrol',
                transmission='automatic',
                asking_price=50000,
                listing_duration=30,
                location='Miami, FL',
                engine_type='V6',
                displacement='3.0L',
                power='300hp',
                torque='300Nm',
                fuel_tank='60L',
                doors=4,
                seating=5,
                weight='1500kg'
            )

        # Vehicle & Reel for used_gen
        self.vehicle_ai = create_vehicle('AI Car')
        self.reel_ai = DealerVehicleReel.objects.create(
            dealer=self.dealer,
            vehicle=self.vehicle_ai,
            video_file='test_ai.mp4',
            is_ai_generated=True,
            ai_generation=self.used_gen
        )
        # Manual Vehicle & Reel
        self.vehicle_manual = create_vehicle('Manual Car')
        self.reel_manual = DealerVehicleReel.objects.create(
            dealer=self.dealer,
            vehicle=self.vehicle_manual,
            video_file='test_manual.mp4',
            is_ai_generated=False
        )

    def test_buyer_forbidden_from_ai_video_list(self):
        self.client.force_authenticate(user=self.buyer)
        response = self.client.get('/api/vehicles/ai-video/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dealer_list_all_ai_videos(self):
        self.client.force_authenticate(user=self.dealer)
        response = self.client.get('/api/vehicles/ai-video/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_dealer_filter_unused_ai_videos(self):
        self.client.force_authenticate(user=self.dealer)
        response = self.client.get('/api/vehicles/ai-video/?unused=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['job_id'], str(self.unused_gen.job_id))
        self.assertFalse(response.data[0]['is_used'])

    def test_dealer_inventory_filter_ai_generated(self):
        self.client.force_authenticate(user=self.dealer)
        response = self.client.get('/api/vehicles/inventory/?is_ai_generated=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.reel_ai.id)
        self.assertTrue(response.data[0]['is_ai_generated'])

    def test_dealer_inventory_filter_manual(self):
        self.client.force_authenticate(user=self.dealer)
        response = self.client.get('/api/vehicles/inventory/?is_ai_generated=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.reel_manual.id)
        self.assertFalse(response.data[0]['is_ai_generated'])
