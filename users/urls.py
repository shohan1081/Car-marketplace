from django.urls import path
from .views import (
    BuyerSignupView, DealerSignupView, LoginView, OTPVerifyView, 
    UserPreferenceView, BusinessInformationView, FirebaseAuthView,
    ForgetPasswordView, ResetPasswordView, DealerProfileView, DealerReviewView,
    UserProfileView
)

urlpatterns = [
    # Buyer URLs
    path('buyer/signup/', BuyerSignupView.as_view(), name='buyer-signup'),
    path('buyer/login/', LoginView.as_view(), name='buyer-login'),
    
    # Dealer URLs
    path('dealer/signup/', DealerSignupView.as_view(), name='dealer-signup'),
    path('dealer/login/', LoginView.as_view(), name='dealer-login'),
    path('dealer/business-info/', BusinessInformationView.as_view(), name='business-info'),

    # Shared URLs
    path('otp-verify/', OTPVerifyView.as_view(), name='otp-verify'),
    path('forget-password/', ForgetPasswordView.as_view(), name='forget-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('firebase-auth/', FirebaseAuthView.as_view(), name='firebase-auth'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('buyer/preferences/', UserPreferenceView.as_view(), name='user-preferences'),
    path('dealer/profile/<int:pk>/', DealerProfileView.as_view(), name='dealer-profile'),
    path('dealer/profile/<int:pk>/review/', DealerReviewView.as_view(), name='dealer-review'),
]
