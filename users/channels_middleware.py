from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from jwt import decode as jwt_decode
from django.conf import settings

User = get_user_model()

@database_sync_to_async
def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()

class JWTAuthMiddleware:
    """
    Custom middleware that populates scope['user'] from a JWT token in the query string.
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # Parse the query string
        query_string = scope.get('query_string', b'').decode()
        print(f"WebSocket Handshake Query String: {query_string}")
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        if token:
            print(f"Token found in query string: {token[:10]}...")
            try:
                # Validate the token
                UntypedToken(token)
                
                # Decode the token to get the user ID
                decoded_data = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                user_id = decoded_data.get(settings.SIMPLE_JWT.get('USER_ID_CLAIM', 'user_id'))
                
                # Get the user from the database
                scope['user'] = await get_user(user_id)
                print(f"User authenticated: {scope['user']}")
            except (InvalidToken, TokenError, Exception) as e:
                print(f"JWT Auth Error: {str(e)}")
                # If token is invalid, set user as Anonymous
                scope['user'] = AnonymousUser()
        else:
            print("No token found in query string.")
            scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)
