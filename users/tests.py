from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()

class UserSearchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create Dealers
        self.dealer1 = User.objects.create_user(
            email='shohan_dealer@example.com',
            password='password123',
            full_name='Shohan Dealer',
            is_dealer=True,
            is_verified=True
        )
        self.dealer2 = User.objects.create_user(
            email='other_dealer@example.com',
            password='password123',
            full_name='Other Dealer',
            is_dealer=True,
            is_verified=True
        )
        
        # Create Buyers
        self.buyer1 = User.objects.create_user(
            email='shohan_buyer@example.com',
            password='password123',
            full_name='Shohan Buyer',
            is_buyer=True,
            is_verified=True
        )
        self.buyer2 = User.objects.create_user(
            email='buyer2@example.com',
            password='password123',
            full_name='Alice Smith',
            is_buyer=True,
            is_verified=True
        )

    def test_buyer_searches_dealer_prefix_name(self):
        self.client.force_authenticate(user=self.buyer1)
        response = self.client.get('/api/users/search/?q=sh')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only find dealer1 (Shohan Dealer)
        # Should NOT find buyer1 (himself) or buyer2
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['email'], self.dealer1.email)

    def test_dealer_searches_buyer_prefix_email(self):
        self.client.force_authenticate(user=self.dealer1)
        # Search for 'sh' which matches shohan_buyer@example.com
        response = self.client.get('/api/users/search/?q=sh')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should find buyer1 (shohan_buyer@example.com)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['email'], self.buyer1.email)

    def test_role_separation(self):
        self.client.force_authenticate(user=self.buyer1)
        # Search for 'Al' which matches Alice Smith (buyer2)
        response = self.client.get('/api/users/search/?q=Al')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should find NOTHING because Alice is a Buyer and we are a Buyer
        self.assertEqual(len(response.data), 0)

    def test_empty_query(self):
        self.client.force_authenticate(user=self.buyer1)
        response = self.client.get('/api/users/search/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
