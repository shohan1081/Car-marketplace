from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from vehicles.models import Vehicle, DealerVehicleReel, Music
from messaging.models import Conversation

User = get_user_model()

class DirectChatTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create a dealer
        self.dealer = User.objects.create_user(
            email='dealer@example.com',
            password='password123',
            is_dealer=True,
            is_verified=True
        )
        
        # Create a buyer
        self.buyer = User.objects.create_user(
            email='buyer@example.com',
            password='password123',
            is_buyer=True,
            is_verified=True
        )
        
        # Create a vehicle and reel
        self.vehicle = Vehicle.objects.create(
            dealer=self.dealer,
            name='Test Car',
            model='X5',
            description='Test Description',
            year=2023,
            variant='Luxury',
            body_type='suv',
            condition='new',
            mileage_km=0,
            color='Black',
            fuel_type='petrol',
            transmission='automatic',
            asking_price=50000,
            listing_duration=30,
            location='New York',
            engine_type='V8',
            displacement='4.4L',
            power='523 hp',
            torque='553 lb-ft',
            fuel_tank='21.9 gal',
            doors=5,
            seating=5,
            weight='5,000 lbs',
            upholstery='Leather',
            windows='Power',
            is_draft=False
        )
        
        # Need a dummy video file for the reel (or just mock it if validator is strict)
        # For testing purposes, we might need to bypass the moviepy validator if it runs on save
        self.reel = DealerVehicleReel.objects.create(
            dealer=self.dealer,
            vehicle=self.vehicle,
            video_file='test_video.mp4' # This might fail if the validator is active during create
        )

    def test_start_chat_success(self):
        self.client.force_authenticate(user=self.buyer)
        response = self.client.post('/api/messaging/start-chat/', {'reel_id': self.reel.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('conversation_id', response.data)
        
        # Verify conversation in DB
        conv_id = response.data['conversation_id']
        conversation = Conversation.objects.get(id=conv_id)
        self.assertEqual(conversation.reel, self.reel)
        self.assertTrue(conversation.participants.filter(id=self.buyer.id).exists())
        self.assertTrue(conversation.participants.filter(id=self.dealer.id).exists())

    def test_start_chat_reuse_existing(self):
        self.client.force_authenticate(user=self.buyer)
        
        # First call
        response1 = self.client.post('/api/messaging/start-chat/', {'reel_id': self.reel.id})
        id1 = response1.data['conversation_id']
        
        # Second call
        response2 = self.client.post('/api/messaging/start-chat/', {'reel_id': self.reel.id})
        id2 = response2.data['conversation_id']
        
        self.assertEqual(id1, id2)
        self.assertEqual(Conversation.objects.filter(reel=self.reel, participants=self.buyer).count(), 1)

    def test_start_chat_with_self_fails(self):
        self.client.force_authenticate(user=self.dealer)
        response = self.client.post('/api/messaging/start-chat/', {'reel_id': self.reel.id})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], "You cannot start a chat with yourself.")

    def test_start_chat_invalid_reel(self):
        self.client.force_authenticate(user=self.buyer)
        response = self.client.post('/api/messaging/start-chat/', {'reel_id': 999})
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
