from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
from decimal import Decimal

User = get_user_model()

def generate_uuid():
    """Generate a unique venture ID"""
    return f"{uuid.uuid4().hex[:8].upper()}"

class Venture(models.Model):
    """Investment venture/initiative"""
    VENTURE_TYPES = [
        ('agriculture', 'Agriculture'),
        ('tech', 'Technology'),
        ('real_estate', 'Real Estate'),
        ('manufacturing', 'Manufacturing'),
        ('renewable', 'Renewable Energy'),
        ('healthcare', 'Healthcare'),
        ('creative', 'Creative Industries'),
    ]
    
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    

    # Basic Info
    code = models.CharField(max_length=20, unique=True, default=generate_uuid)
    name = models.CharField(max_length=200)
    description = models.TextField()
    venture_type = models.CharField(max_length=50, choices=VENTURE_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    
    # Financial Details
    total_value = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    minimum_investment = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('500.00'))
    shares_available = models.IntegerField(default=1000)
    shares_issued = models.IntegerField(default=0)
    price_per_share = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    
    # Governance
    governance_board = models.ManyToManyField(User, related_name='governed_ventures', blank=True)
    risk_level = models.IntegerField(choices=[(1, 'Low'), (2, 'Medium'), (3, 'High')], default=2)
    
    # Timeline
    start_date = models.DateField()
    expected_end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        # Auto-calculate price per share
        if self.total_value and self.shares_available:
            self.price_per_share = self.total_value / Decimal(self.shares_available)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.code}: {self.name}"
    
    @property
    def available_shares(self):
        return self.shares_available - self.shares_issued
    
    @property
    def percentage_funded(self):
        if self.shares_available == 0:
            return 0
        return (self.shares_issued / self.shares_available) * 100
    
    @property
    def is_open_for_investment(self):
        return self.status == 'active' and self.available_shares > 0
    
    

class VentureDocument(models.Model):
    """Documents related to ventures"""
    venture = models.ForeignKey(Venture, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=200)
    document_type = models.CharField(max_length=50, choices=[
        ('proposal', 'Business Proposal'),
        ('legal', 'Legal Document'),
        ('financial', 'Financial Report'),
        ('governance', 'Governance Document'),
        ('other', 'Other')
    ])
    file = models.FileField(upload_to='venture_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-uploaded_at']

class Investment(models.Model):
    """Individual investments in ventures"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('active', 'Active'),
        ('matured', 'Matured'),
        ('cancelled', 'Cancelled'),
    ]
    ACTIVE_STATUSES = ['confirmed', 'active']

    # Basic Info
    investor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investments')
    venture = models.ForeignKey(Venture, on_delete=models.CASCADE, related_name='investments')
    reference = models.CharField(max_length=50, unique=True, default=generate_uuid)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Investment Details
    shares = models.IntegerField(validators=[MinValueValidator(1)])
    amount_invested = models.DecimalField(max_digits=14, decimal_places=2)
    share_price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    # Dates
    invested_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    maturity_date = models.DateField(null=True, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-invested_at']
        unique_together = ['investor', 'venture']
    
    def __str__(self):
        return f"{self.reference}: {self.investor.email} - {self.venture.name}"
    
    @property
    def current_value(self):
        if not self.venture.price_per_share:
            return self.amount_invested
        return self.shares * self.venture.price_per_share
    
    @property
    def profit_loss(self):
        return self.current_value - self.amount_invested
    
    @property
    def is_active(self):
        return self.status in ['confirmed', 'active']

class Dividend(models.Model):
    """Dividend payments to investors"""
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name='dividends')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()
    payment_date = models.DateField()
    reference = models.CharField(max_length=50, unique=True, default=generate_uuid)
    
    # Payment Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ], default='pending')
    
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-payment_date']



class AuditLog(models.Model):
    """System audit trail"""
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('investment', 'Investment'),
        ('payment', 'Payment'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="core_audit_log")
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    
    # Details
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.created_at}: {self.user.email if self.user else 'System'} - {self.action}"

class UserPortfolio(models.Model):
    """User's investment portfolio summary"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='portfolio')
    
    # Portfolio Summary
    total_invested = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    current_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_dividends = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    # Statistics
    active_investments = models.IntegerField(default=0)
    completed_investments = models.IntegerField(default=0)
    total_investments = models.IntegerField(default=0)
    
    # Performance
    average_return = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    def update_portfolio(self):
        """Update portfolio statistics"""
        investments = self.user.investments.filter(status__in=['confirmed', 'active', 'matured'])
        
        self.total_investments = investments.count()
        self.active_investments = investments.filter(status__in=['confirmed', 'active']).count()
        self.completed_investments = investments.filter(status='matured').count()
        
        # Calculate totals
        self.total_invested = sum(inv.amount_invested for inv in investments)
        self.current_value = sum(inv.current_value for inv in investments)
        
        # Calculate dividends
        dividends = Dividend.objects.filter(
            investment__in=investments,
            status='paid'
        )
        self.total_dividends = sum(div.amount for div in dividends)
        
        # Calculate average return (simplified)
        if self.total_invested > 0:
            total_gain = (self.current_value - self.total_invested) + self.total_dividends
            self.average_return = (total_gain / self.total_invested) * 100
        
        self.save()
    
    def __str__(self):
        return f"Portfolio: {self.user.email}"

class Notification(models.Model):
    """User notifications"""
    NOTIFICATION_TYPES = [
        ('investment', 'Investment Update'),
        ('dividend', 'Dividend Payment'),
        ('venture', 'Venture Update'),
        ('system', 'System Notification'),
        ('security', 'Security Alert'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related objects
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, null=True, blank=True)
    venture = models.ForeignKey(Venture, on_delete=models.CASCADE, null=True, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.email}"