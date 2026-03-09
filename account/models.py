from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.core.validators import MinLengthValidator, RegexValidator
import uuid
from decimal import Decimal

#===============================================================================
# CHOICES
#===============================================================================

class AgeGroupChoices(models.TextChoices):
    AGE_18_24 = '18-24', '18-24 Years'
    AGE_25_29 = '25-29', '25-29 Years'
    AGE_30_35 = '30-35', '30-35 Years'

class OTPPurposeChoices(models.TextChoices):
    VERIFICATION = 'verification', 'Email Verification'
    PASSWORD_RESET = 'password_reset', 'Password Reset'
    LOGIN = 'login', 'Two-Factor Authentication'

class HederaAccountStatusChoices(models.TextChoices):
    ACTIVE = 'active', 'Active'
    PENDING = 'pending_creation', 'Pending Creation'
    FAILED = 'creation_failed', 'Creation Failed'

class TransactionStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SUCCESS = 'success', 'Success'
    FAILED = 'failed', 'Failed'

class TokenTypeChoices(models.TextChoices):
    HBAR = 'hbar', 'HBAR'
    FUNGIBLE = 'fungible', 'Fungible Token'
    NFT = 'nft', 'Non-Fungible Token'


#===============================================================================
# USER MANAGER
#===============================================================================

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        return self.create_user(email, password, **extra_fields)


#===============================================================================
# USER MODEL
#===============================================================================
# models.py - Simplified User model

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True, db_index=True)
    
    # Profile
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    id_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    country = models.CharField(max_length=100, default='Kenya')
    county = models.CharField(max_length=100, null=True, blank=True)
    
    # Status
    is_verified = models.BooleanField(default=False)
    is_youth = models.BooleanField(default=True)
    age_group = models.CharField(max_length=5, choices=AgeGroupChoices.choices, null=True, blank=True)
    
    # Password reset
    reset_token = models.UUIDField(default=uuid.uuid4, editable=False, null=True, blank=True)
    reset_token_expires = models.DateTimeField(null=True, blank=True)
    
    # Hedera integration (minimal fields)
    hedera_account_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    hedera_public_key = models.TextField(null=True, blank=True)
    hedera_private_key_encrypted = models.TextField(null=True, blank=True)
    hedera_account_status = models.CharField(
        max_length=20,
        choices=HederaAccountStatusChoices.choices,
        default=HederaAccountStatusChoices.PENDING,
        null=True,
        blank=True
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    objects = CustomUserManager()

    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def has_hedera_account(self):
        return bool(self.hedera_account_id)

#===============================================================================
# OTP MODEL
#===============================================================================

class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6, validators=[MinLengthValidator(6)])
    purpose = models.CharField(max_length=20, choices=OTPPurposeChoices.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'purpose', 'is_used']),
            models.Index(fields=['code', 'expires_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.purpose}"

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at


#===============================================================================
# USER SESSION MODEL
#===============================================================================

class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=100)
    device_info = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_activity']
        indexes = [models.Index(fields=['session_key'])]

    def __str__(self):
        return f"{self.user.email} - {self.created_at.date()}"


#===============================================================================
# AUDIT LOG MODEL
#===============================================================================

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    details = models.JSONField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['user', '-timestamp'])]

    def __str__(self):
        return f"{self.user.email if self.user else 'Anonymous'} - {self.action}"

    @classmethod
    def log(cls, user, action, details=None, request=None):
        ip = None
        agent = None
        if request:
            x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')
            agent = request.META.get('HTTP_USER_AGENT', '')
        
        return cls.objects.create(
            user=user,
            action=action,
            details=details or {},
            ip_address=ip,
            user_agent=agent
        )


#===============================================================================
# HEDERA TRANSACTION MODEL
#===============================================================================

class HederaTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hedera_transactions')
    transaction_id = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    token_type = models.CharField(max_length=20, choices=TokenTypeChoices.choices, default=TokenTypeChoices.HBAR)
    token_id = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, choices=TransactionStatusChoices.choices, default=TransactionStatusChoices.PENDING)
    consensus_timestamp = models.DateTimeField(null=True, blank=True)
    from_account = models.CharField(max_length=50)
    to_account = models.CharField(max_length=50)
    memo = models.TextField(null=True, blank=True)
    charged_fees = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['transaction_id']),
        ]

    def __str__(self):
        return f"{self.transaction_id[:8]}... - {self.amount} HBAR"


#===============================================================================
# TOKEN BALANCE MODEL
#===============================================================================

class TokenBalance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='token_balances')
    token_id = models.CharField(max_length=50)
    token_name = models.CharField(max_length=100, null=True, blank=True)
    token_symbol = models.CharField(max_length=20, null=True, blank=True)
    token_type = models.CharField(max_length=20, choices=TokenTypeChoices.choices)
    balance = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal('0'))
    serial_numbers = models.JSONField(null=True, blank=True)  # For NFTs
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'token_id']
        indexes = [models.Index(fields=['user', 'token_type'])]

    def __str__(self):
        if self.token_type == TokenTypeChoices.NFT:
            return f"{self.user.email} - {self.token_symbol}: {len(self.serial_numbers or [])} NFTs"
        return f"{self.user.email} - {self.token_symbol}: {self.balance}"