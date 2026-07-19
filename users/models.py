from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    
    is_buyer = models.BooleanField(default=False)
    is_dealer = models.BooleanField(default=False)
    
    full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    profile_photo = models.ImageField(upload_to='profiles/', null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    
    is_verified = models.BooleanField(default=False)
    last_active = models.DateTimeField(null=True, blank=True)


    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

    @property
    def is_online(self):
        from django.utils import timezone
        import datetime
        if self.last_active:
            now = timezone.now()
            return now - self.last_active < datetime.timedelta(minutes=5)
        return False

class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - {self.code}"

class UserPreference(models.Model):
    VEHICLE_CHOICES = [
        ('sedan', 'Sedan'),
        ('suv', 'SUV'),
        ('hatchback', 'Hatchback'),
        ('van', 'Van'),
        ('electric', 'Electric'),
    ]
    FUEL_CHOICES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('hybrid', 'Hybrid'),
        ('cng', 'CNG'),
        ('electric', 'Electric'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    vehicle_types = models.JSONField(default=list, blank=True, null=True)
    budget_range = models.CharField(max_length=100, blank=True, null=True)
    fuel_preference = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Preferences for {self.user.email}"

class BusinessInformation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    SPECIALIZATION_CHOICES = [
        ('new_cars', 'New Cars'),
        ('used_cars', 'Used Cars'),
        ('luxury', 'Luxury'),
        ('commercial', 'Commercial'),
        ('electric', 'Electric'),
        ('motorcycles', 'Motorcycles'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='business_info')
    verification_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)
    rejected_fields = models.JSONField(default=list, blank=True, null=True)
    
    dealership_name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    specialization = models.JSONField(default=list)
    
    street_address = models.CharField(max_length=255)
    state = models.CharField(max_length=100)
    division = models.CharField(max_length=100)
    
    business_website = models.URLField(blank=True, null=True)
    trade_license_number = models.CharField(max_length=100, blank=True, null=True)
    dealership_license_document = models.ImageField(upload_to='licenses/', blank=True, null=True)
    dealership_license_number = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    
    dealership_logo = models.ImageField(upload_to='dealer_logos/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='dealer_covers/', blank=True, null=True)
    dealership_description = models.TextField(blank=True, null=True)
    operating_hours = models.JSONField(default=dict, blank=True, null=True)
    
    facebook_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)

    # Map Location
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Reputation metrics (can be calculated or cached)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    review_count = models.PositiveIntegerField(default=0)
    follower_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.dealership_name

class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    dealer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'dealer')

    def __str__(self):
        return f"{self.follower.email} follows {self.dealer.email}"

class DealerReview(models.Model):
    dealer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    rating = models.PositiveSmallIntegerField() # 1-5
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('dealer', 'reviewer')

    def __str__(self):
        return f"Review for {self.dealer.email} by {self.reviewer.email}"
