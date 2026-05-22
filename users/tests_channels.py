from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from users.channels_middleware import JWTAuthMiddleware
import asyncio

User = get_user_model()

class MockInnerApp:
    def __init__(self):
        self.called = False
        self.scope = None

    async def __call__(self, scope, receive, send):
        self.called = True
        self.scope = scope

class JWTAuthMiddlewareTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='password123'
        )
        self.token = str(AccessToken.for_user(self.user))

    def test_valid_token(self):
        inner = MockInnerApp()
        middleware = JWTAuthMiddleware(inner)
        
        # Simulate scope with token
        scope = {
            'type': 'websocket',
            'query_string': f'token={self.token}'.encode()
        }
        
        # Run middleware
        asyncio.run(middleware(scope, None, None))
        
        self.assertTrue(inner.called)
        self.assertEqual(inner.scope['user'], self.user)

    def test_invalid_token(self):
        inner = MockInnerApp()
        middleware = JWTAuthMiddleware(inner)
        
        # Simulate scope with invalid token
        scope = {
            'type': 'websocket',
            'query_string': b'token=invalidtoken'
        }
        
        # Run middleware
        asyncio.run(middleware(scope, None, None))
        
        self.assertTrue(inner.called)
        self.assertIsInstance(inner.scope['user'], AnonymousUser)

    def test_no_token(self):
        inner = MockInnerApp()
        middleware = JWTAuthMiddleware(inner)
        
        # Simulate scope without token
        scope = {
            'type': 'websocket',
            'query_string': b''
        }
        
        # Run middleware
        asyncio.run(middleware(scope, None, None))
        
        self.assertTrue(inner.called)
        self.assertIsInstance(inner.scope['user'], AnonymousUser)
