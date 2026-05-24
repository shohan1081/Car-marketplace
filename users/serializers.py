from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserPreference, OTP, BusinessInformation

User = get_user_model()

class BuyerSignupSerializer(serializers.ModelSerializer):
    re_enter_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['full_name', 'email', 'location', 'profile_photo', 'password', 're_enter_password']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if data['password'] != data['re_enter_password']:
            raise serializers.ValidationError({"password": "Passwords must match."})
        return data

    def create(self, validated_data):
        validated_data.pop('re_enter_password')
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data.get('full_name', ''),
            location=validated_data.get('location', ''),
            profile_photo=validated_data.get('profile_photo', None),
            is_buyer=True
        )
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=4)

class ForgetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=4)
    new_password = serializers.CharField(write_only=True)

class DealerSignupSerializer(serializers.ModelSerializer):
    re_enter_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone_number', 'designation', 'password', 're_enter_password']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if data['password'] != data['re_enter_password']:
            raise serializers.ValidationError({"password": "Passwords must match."})
        return data

    def create(self, validated_data):
        validated_data.pop('re_enter_password')
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data.get('full_name', ''),
            phone_number=validated_data.get('phone_number', ''),
            designation=validated_data.get('designation', ''),
            is_dealer=True
        )
        return user

class BusinessInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessInformation
        fields = '__all__'
        read_only_fields = ['user', 'verification_status', 'rejection_reason', 'rating', 'review_count', 'follower_count', 'share_count']


    def validate_specialization(self, value):
        valid_choices = [choice[0] for choice in BusinessInformation.SPECIALIZATION_CHOICES]
        for s in value:
            if s not in valid_choices:
                raise serializers.ValidationError(f"{s} is not a valid specialization.")
        return value

class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ['vehicle_types', 'budget_range', 'fuel_preference', 'city']

    def validate_vehicle_types(self, value):
        valid_types = [choice[0] for choice in UserPreference.VEHICLE_CHOICES]
        for t in value:
            if t not in valid_types:
                raise serializers.ValidationError(f"{t} is not a valid vehicle type.")
        return value

    def validate_fuel_preference(self, value):
        valid_fuels = [choice[0] for choice in UserPreference.FUEL_CHOICES]
        if value not in valid_fuels:
            raise serializers.ValidationError(f"{value} is not a valid fuel preference.")
        return value

class UserProfileSerializer(serializers.ModelSerializer):
    preferences = UserPreferenceSerializer(read_only=True)
    business_info = BusinessInformationSerializer(read_only=True)
    subscription = serializers.SerializerMethodField()
    activities = serializers.SerializerMethodField()
    saved_reels_count = serializers.SerializerMethodField()
    unread_messages_count = serializers.SerializerMethodField()
    verification_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'phone_number', 'designation', 'profile_photo', 'location', 
            'preferences', 'business_info', 'subscription',
            'activities', 'saved_reels_count', 'unread_messages_count',
            'verification_status', 'is_buyer', 'is_dealer'
        ]

    def get_subscription(self, obj):
        if not obj.is_dealer:
            return None
        from subscriptions.serializers import DealerSubscriptionSerializer
        try:
            return DealerSubscriptionSerializer(obj.subscription).data
        except Exception:
            return None

    def get_verification_status(self, obj):
        if obj.is_dealer:
            try:
                return obj.business_info.verification_status
            except BusinessInformation.DoesNotExist:
                return 'not_submitted'
        return 'n/a'

    def get_saved_reels_count(self, obj):
        from vehicles.models import SavedReel
        return SavedReel.objects.filter(user=obj).count()

    def get_unread_messages_count(self, obj):
        from messaging.models import Message
        return Message.objects.filter(
            conversation__participants=obj, 
            is_read=False
        ).exclude(sender=obj).count()

    def get_activities(self, obj):
        from vehicles.models import Like, SavedReel
        from vehicles.serializers import ReelNewsfeedSerializer
        
        # Get last 5 likes
        recent_likes = Like.objects.filter(user=obj).order_by('-created_at')[:5]
        # Get last 5 saves
        recent_saves = SavedReel.objects.filter(user=obj).order_by('-created_at')[:5]
        
        activities = []
        
        for like in recent_likes:
            activities.append({
                'type': 'like',
                'created_at': like.created_at,
                'reel': ReelNewsfeedSerializer(like.reel, context=self.context).data
            })
            
        for save in recent_saves:
            activities.append({
                'type': 'save',
                'created_at': save.created_at,
                'reel': ReelNewsfeedSerializer(save.reel, context=self.context).data
            })
            
        # Sort combined activities by date
        activities.sort(key=lambda x: x['created_at'], reverse=True)
        return activities[:10]

from .models import DealerReview

class DealerReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.full_name', read_only=True)

    class Meta:
        model = DealerReview
        fields = ['id', 'reviewer_name', 'rating', 'comment', 'created_at']

class PublicBusinessInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessInformation
        fields = [
            'dealership_name', 'display_name', 'specialization', 
            'street_address', 'state', 'division', 
            'business_website', 'dealership_logo', 'cover_image', 
            'dealership_description', 'operating_hours', 
            'facebook_url', 'instagram_url', 
            'rating', 'review_count', 'follower_count', 'share_count', 'verification_status'
        ]

class DealerProfileSerializer(serializers.ModelSerializer):
    business_info = PublicBusinessInformationSerializer(read_only=True)
    reviews = DealerReviewSerializer(source='reviews_received', many=True, read_only=True)
    is_following = serializers.SerializerMethodField()
    reels = serializers.SerializerMethodField()
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'profile_photo', 'business_info', 'reviews', 'is_following', 'reels', 'share_url']

    def get_share_url(self, obj):
        return f"https://yourapp.com/dealer/{obj.id}" # Placeholder URL

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from .models import Follow
            return Follow.objects.filter(follower=request.user, dealer=obj).exists()
        return False

    def get_reels(self, obj):
        from vehicles.models import DealerVehicleReel
        from vehicles.serializers import ReelNewsfeedSerializer
        
        # Only show published (not draft) reels
        reels = DealerVehicleReel.objects.filter(dealer=obj, vehicle__is_draft=False).order_by('-created_at')
        return ReelNewsfeedSerializer(reels, many=True, context=self.context).data

class UserSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'profile_photo', 'is_buyer', 'is_dealer']

class FollowerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'profile_photo']
