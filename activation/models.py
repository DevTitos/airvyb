from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
from finance.models import Transaction
User = get_user_model()

def generate_uuid():
    """Generate a unique ID"""
    return f"{uuid.uuid4().hex[:12].upper()}"

class MemberActivation(models.Model):
    """Member activation and membership management"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('processing', 'Processing'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHODS = [
        ('mpesa', 'M-Pesa'),
        ('wallet', 'Wallet Balance'),
    ]
    
    # Basic Info
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='activation')
    reference = models.CharField(max_length=50, unique=True, default=generate_uuid)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment Details
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=100.00, validators=[MinValueValidator(100)])
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='mpesa')
    phone_number = models.CharField(max_length=15, blank=True)
    mpesa_code = models.CharField(max_length=50, blank=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='activation')
    
    # Membership Details
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['reference']),
            models.Index(fields=['mpesa_code']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.status} - {self.reference}"
    
    def activate(self):
        """Activate membership"""
        self.status = 'active'
        self.activated_at = timezone.now()
        self.expires_at = timezone.now() + timezone.timedelta(days=365)  # 1 year membership
        self.save()
    
    @property
    def is_active(self):
        """Check if membership is active"""
        return self.status == 'active' and self.expires_at and self.expires_at > timezone.now()
    
    @property
    def days_remaining(self):
        """Get days remaining in membership"""
        if self.expires_at:
            delta = self.expires_at - timezone.now()
            return max(0, delta.days)
        return 0
    
    @property
    def progress_percentage(self):
        """Get membership progress percentage"""
        if self.activated_at and self.expires_at:
            total = (self.expires_at - self.activated_at).days
            remaining = (self.expires_at - timezone.now()).days
            if total > 0:
                return ((total - remaining) / total) * 100
        return 0


class MembershipBenefit(models.Model):
    """Membership benefits and features"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Font Awesome icon class")
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class ActivationPromo(models.Model):
    """Promotional codes for activation"""
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    discount_percent = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    max_uses = models.IntegerField(default=1)
    current_uses = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-valid_from']
    
    def __str__(self):
        return f"{self.code} - {self.discount_percent}% off"
    
    @property
    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active and
            self.current_uses < self.max_uses and
            self.valid_from <= now <= self.valid_to
        )
    
    def calculate_discount(self, amount):
        """Calculate discounted amount"""
        if self.is_valid:
            return amount * (self.discount_percent / 100)
        return 0