import random
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail
from django.conf import settings
from .serializers import (
    BuyerSignupSerializer, DealerSignupSerializer, LoginSerializer, OTPVerifySerializer,
    ForgetPasswordSerializer, ResetPasswordSerializer, UserPreferenceSerializer,
    BusinessInformationSerializer
)
from .models import OTP, UserPreference, BusinessInformation
from rest_framework.authtoken.models import Token

User = get_user_model()

def generate_otp(user):
    code = str(random.randint(100000, 999999))
    OTP.objects.create(user=user, code=code)
    # In production, use a background task to send email
    # send_mail(
    #     'Your OTP Code',
    #     f'Your OTP code is {code}',
    #     settings.EMAIL_HOST_USER,
    #     [user.email],
    #     fail_silently=False,
    # )
    print(f"OTP for {user.email}: {code}") # For development
    return code

class BuyerSignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = BuyerSignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            generate_otp(user)
            return Response({"message": "Signup successful. OTP sent to email."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class OTPVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            code = serializer.validated_data['code']
            try:
                user = User.objects.get(email=email)
                otp = OTP.objects.filter(user=user, code=code, is_used=False).last()
                if otp:
                    otp.is_used = True
                    otp.save()
                    user.is_verified = True
                    user.save()
                    token, _ = Token.objects.get_or_create(user=user)
                    return Response({"message": "OTP verified successfully.", "token": token.key}, status=status.HTTP_200_OK)
                return Response({"error": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            user = authenticate(email=email, password=password)
            if user:
                if not user.is_verified:
                    return Response({"error": "Please verify your email first."}, status=status.HTTP_401_UNAUTHORIZED)
                token, _ = Token.objects.get_or_create(user=user)
                return Response({
                    "token": token.key, 
                    "is_buyer": user.is_buyer,
                    "is_dealer": user.is_dealer
                }, status=status.HTTP_200_OK)
            return Response({"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DealerSignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = DealerSignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            generate_otp(user)
            return Response({"message": "Dealer signup successful. OTP sent to email."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BusinessInformationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can set business information."}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            info = request.user.business_info
            if info.verification_status == 'verified':
                return Response({"error": "Verified accounts cannot modify business information directly. Please contact support."}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = BusinessInformationSerializer(info, data=request.data, partial=True)
        except BusinessInformation.DoesNotExist:
            serializer = BusinessInformationSerializer(data=request.data)

        if serializer.is_valid():
            # When updating or creating, set status back to pending
            business_info = serializer.save(user=request.user, verification_status='pending', rejection_reason=None)
            return Response({
                "message": "Business information submitted for verification.",
                "status": business_info.verification_status
            }, status=status.HTTP_201_CREATED if not hasattr(request.user, 'business_info') else status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            info = request.user.business_info
            serializer = BusinessInformationSerializer(info)
            return Response(serializer.data)
        except BusinessInformation.DoesNotExist:
            return Response({"error": "Business information not found."}, status=status.HTTP_404_NOT_FOUND)

class UserPreferenceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = UserPreferenceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({"message": "Preferences saved successfully."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            prefs = request.user.preferences
            serializer = UserPreferenceSerializer(prefs)
            return Response(serializer.data)
        except UserPreference.DoesNotExist:
            return Response({"error": "Preferences not found."}, status=status.HTTP_404_NOT_FOUND)

# Placeholder for Firebase Social Auth (Google, Apple, etc.)
class FirebaseAuthView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Implementation logic for Firebase token verification:
        # 1. Receive firebase_token from request.data
        # 2. Verify token with firebase_admin SDK
        # 3. Get or Create user based on firebase UID/Email
        # 4. Return local Auth Token
        return Response({"message": "Firebase authentication structure ready."}, status=status.HTTP_200_OK)

class ForgetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                generate_otp(user)
                return Response({"message": "OTP sent to your email for password reset."}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({"error": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            code = serializer.validated_data['code']
            new_password = serializer.validated_data['new_password']
            try:
                user = User.objects.get(email=email)
                otp = OTP.objects.filter(user=user, code=code, is_used=False).last()
                if otp:
                    otp.is_used = True
                    otp.save()
                    user.set_password(new_password)
                    user.save()
                    return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)
                return Response({"error": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
