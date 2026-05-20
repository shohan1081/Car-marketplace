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
    BusinessInformationSerializer, DealerProfileSerializer, DealerReviewSerializer,
    UserProfileSerializer
)
from .models import OTP, UserPreference, BusinessInformation, DealerReview
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Avg

User = get_user_model()

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def generate_otp(user):
    code = str(random.randint(1000, 9999))
    OTP.objects.create(user=user, code=code)
    
    subject = 'Your OTP Code - Auto Marketplace'
    message = f'Hello {user.full_name or "User"},\n\nYour OTP code for verification is: {code}\n\nThank you!'
    email_from = getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER)
    recipient_list = [user.email]
    
    error_msg = None
    try:
        send_mail(subject, message, email_from, recipient_list, fail_silently=False)
    except Exception as e:
        error_msg = str(e)
        print(f"Failed to send email to {user.email}: {e}")
        
    print(f"OTP for {user.email}: {code}") 
    return code, error_msg

class BuyerSignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = BuyerSignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            _, email_error = generate_otp(user)
            response_data = {"message": "Signup successful. OTP sent to email."}
            if email_error:
                response_data["email_error"] = f"Technical issue sending email: {email_error}. Please check your SMTP settings."
            return Response(response_data, status=status.HTTP_201_CREATED)
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
                    
                    tokens = get_tokens_for_user(user)
                    return Response({
                        "message": "OTP verified successfully.", 
                        "access": tokens['access'],
                        "refresh": tokens['refresh']
                    }, status=status.HTTP_200_OK)
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
                
                tokens = get_tokens_for_user(user)
                return Response({
                    "access": tokens['access'],
                    "refresh": tokens['refresh'],
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
            _, email_error = generate_otp(user)
            response_data = {"message": "Dealer signup successful. OTP sent to email."}
            if email_error:
                response_data["email_error"] = f"Technical issue sending email: {email_error}. Please check your SMTP settings in .env."
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BusinessInformationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can set business information."}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            info = request.user.business_info
            
            # 1. Prevent modification if already verified
            if info.verification_status == 'verified':
                return Response({
                    "error": "Verified accounts cannot modify business information directly. Please contact support."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 2. Prevent modification if already pending
            if info.verification_status == 'pending':
                return Response({
                    "error": "Your information is already under review. Please wait for admin approval."
                }, status=status.HTTP_400_BAD_REQUEST)

            # If it's 'rejected', we allow this update
            serializer = BusinessInformationSerializer(info, data=request.data, partial=True)
            
        except BusinessInformation.DoesNotExist:
            # First time submission
            serializer = BusinessInformationSerializer(data=request.data)

        if serializer.is_valid():
            # Reset status to 'pending' and clear the old rejection reason
            business_info = serializer.save(
                user=request.user, 
                verification_status='pending', 
                rejection_reason=None
            )
            return Response({
                "message": "Business information submitted for verification.",
                "status": business_info.verification_status
            }, status=status.HTTP_200_OK if hasattr(request.user, 'business_info') else status.HTTP_201_CREATED)
            
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

class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data)

class DealerProfileView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        try:
            dealer = User.objects.get(pk=pk, is_dealer=True)
            serializer = DealerProfileSerializer(dealer)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({"error": "Dealer not found."}, status=status.HTTP_404_NOT_FOUND)

class DealerReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            dealer = User.objects.get(pk=pk, is_dealer=True)
            if dealer == request.user:
                return Response({"error": "You cannot review yourself."}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = DealerReviewSerializer(data=request.data)
            if serializer.is_valid():
                review, created = DealerReview.objects.update_or_create(
                    dealer=dealer,
                    reviewer=request.user,
                    defaults={
                        'rating': serializer.validated_data['rating'],
                        'comment': serializer.validated_data['comment']
                    }
                )
                
                # Update Dealer metrics
                stats = DealerReview.objects.filter(dealer=dealer).aggregate(
                    avg_rating=Avg('rating'), 
                    count=models.Count('id')
                )
                info = dealer.business_info
                info.rating = stats['avg_rating']
                info.review_count = stats['count']
                info.save()

                return Response({"message": "Review submitted successfully."}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({"error": "Dealer not found."}, status=status.HTTP_404_NOT_FOUND)
        except BusinessInformation.DoesNotExist:
             return Response({"error": "Dealer business profile not complete."}, status=status.HTTP_400_BAD_REQUEST)
