from django.db import models
from django.conf import settings

class Music(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='music/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Vehicle(models.Model):
    BODY_TYPE_CHOICES = [
        ('sedan', 'Sedan'),
        ('suv', 'SUV'),
        ('hatchback', 'Hatchback'),
        ('pickup', 'Pickup'),
    ]
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('used', 'Used'),
        ('certified', 'Certified Pre-owned'),
    ]
    FUEL_TYPE_CHOICES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('hybrid', 'Hybrid'),
        ('electric', 'Electric'),
        ('cng', 'CNG'),
    ]
    TRANSMISSION_CHOICES = [
        ('automatic', 'Automatic'),
        ('manual', 'Manual'),
        ('cvt', 'CVT'),
    ]
    LISTING_DURATION_CHOICES = [
        (30, '30 Days'),
        (60, '60 Days'),
        (90, '90 Days'),
    ]

    dealer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vehicles')
    
    # Basic Info
    name = models.CharField(max_length=255)
    model = models.CharField(max_length=255)
    description = models.TextField()
    year = models.IntegerField()
    variant = models.CharField(max_length=255)
    body_type = models.CharField(max_length=20, choices=BODY_TYPE_CHOICES)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    mileage_km = models.PositiveIntegerField()
    color = models.CharField(max_length=50)
    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPE_CHOICES)
    transmission = models.CharField(max_length=20, choices=TRANSMISSION_CHOICES)
    asking_price = models.DecimalField(max_digits=12, decimal_places=2)
    negotiable = models.BooleanField(default=False)
    listing_duration = models.IntegerField(choices=LISTING_DURATION_CHOICES)
    location = models.CharField(max_length=255)

    # Technical Specs
    engine_type = models.CharField(max_length=100)
    displacement = models.CharField(max_length=100)
    power = models.CharField(max_length=100)
    torque = models.CharField(max_length=100)
    fuel_tank = models.CharField(max_length=100)
    doors = models.PositiveIntegerField()
    seating = models.PositiveIntegerField()
    weight = models.CharField(max_length=100)

    # Features & Safety
    airbags = models.BooleanField(default=False)
    abs = models.BooleanField(default=False)
    stability_control = models.BooleanField(default=False)
    parking_sensors = models.BooleanField(default=False)
    camera = models.BooleanField(default=False)
    ac = models.BooleanField(default=False)
    infotainment = models.BooleanField(default=False)
    audio = models.BooleanField(default=False)
    upholstery = models.CharField(max_length=100)
    windows = models.CharField(max_length=100)

    is_draft = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} {self.model} ({self.year})"

class DealerVehicleReel(models.Model):
    dealer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reels')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='reels')
    video_file = models.FileField(upload_to='reels/')
    background_music = models.ForeignKey(Music, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reel for {self.vehicle.name} by {self.dealer.email}"
