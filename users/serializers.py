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
    code = serializers.CharField(max_length=6)

class ForgetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
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
        read_only_fields = ['user']

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
