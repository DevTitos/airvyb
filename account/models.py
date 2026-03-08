from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
import uuid

class CustomUserManager(BaseUserManager):
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
    # Remove username field, use email instead
    username = None
    email = models.EmailField(unique=True)
    
    # Additional fields for Airvyb
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    id_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    country = models.CharField(max_length=100, default='Kenya')
    county = models.CharField(max_length=100, null=True, blank=True)
    
    # Account status
    is_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, null=True, blank=True)
    verification_code_expires = models.DateTimeField(null=True, blank=True)
    
    # Youth verification
    is_youth = models.BooleanField(default=True)
    age_group = models.CharField(max_length=20, choices=[
        ('18-24', '18-24 Years'),
        ('25-29', '25-29 Years'),
        ('30-35', '30-35 Years')
    ], null=True, blank=True)
    
    # For password reset
    reset_token = models.UUIDField(default=uuid.uuid4, editable=False, null=True, blank=True)
    reset_token_expires = models.DateTimeField(null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = CustomUserManager()
    
    def __str__(self):
        return self.email
    
    @property
    def is_youth_eligible(self):
        # Calculate if user is within youth age (18-35)
        if self.date_of_birth:
            age = (timezone.now().date() - self.date_of_birth).days // 365
            return 18 <= age <= 35
        return self.is_youth

class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=[
        ('verification', 'Email Verification'),
        ('password_reset', 'Password Reset'),
        ('login', 'Two-Factor Authentication')
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=100)
    device_info = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_activity']

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    details = models.JSONField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']