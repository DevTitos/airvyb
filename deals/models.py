from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from finance.models import Transaction
import uuid

User = get_user_model()

def generate_uuid():
    """Generate a unique ID"""
    return f"{uuid.uuid4().hex[:12].upper()}"

class DealCategory(models.Model):
    """Categories for deals (e.g., M-Pesa Outlet, Service Unit, Asset)"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, help_text="Font Awesome icon class", default="briefcase")
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = "Deal Categories"
    
    def __str__(self):
        return self.name


class Deal(models.Model):
    """Deal sourced by Airvyb Management Ltd (AML)"""
    
    RISK_LEVELS = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
    ]
    
    STATUS_CHOICES = [
        ('sourcing', 'Sourcing'),           # Deal being identified
        ('disclosed', 'Disclosed'),          # Shared with members
        ('opt_in_open', 'Opt-In Open'),      # Members can opt in
        ('opt_in_closed', 'Opt-In Closed'),  # Opt-in period ended
        ('setup', 'Setup'),                   # AML setting up operations
        ('active', 'Active'),                 # Deal running
        ('monitoring', 'Monitoring'),         # Under review
        ('paused', 'Paused'),                  # Temporarily halted
        ('closed', 'Closed'),                  # Deal ended
        ('scaling', 'Scaling'),                # Expanding successful deal
    ]
    
    # Basic Info
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    category = models.ForeignKey(DealCategory, on_delete=models.SET_NULL, null=True, related_name='deals')
    reference = models.CharField(max_length=50, unique=True, default=generate_uuid)
    
    # Deal Details (from AML)
    objective = models.TextField(help_text="Deal objective - what this deal aims to achieve")
    description = models.TextField(help_text="Detailed description of the deal")
    
    # Financials
    opt_in_amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Fixed amount each member pays to opt in"
    )
    total_capital_required = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Total capital needed for the deal"
    )
    min_opt_in_members = models.IntegerField(
        default=1,
        help_text="Minimum members needed for deal to proceed"
    )
    max_opt_in_members = models.IntegerField(
        null=True, blank=True,
        help_text="Maximum members allowed (null = unlimited)"
    )
    
    # Operations
    expected_operations = models.TextField(
        help_text="What the deal will do (not promised returns)"
    )
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS, default='medium')
    duration_months = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Expected duration in months"
    )
    
    # Management
    management_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=10.00,
        help_text="AML management fee percentage of net profit"
    )
    performance_carry_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=20.00,
        help_text="AML performance carry percentage of profits"
    )
    
    # Timeline
    disclosed_at = models.DateTimeField(null=True, blank=True)
    opt_in_start = models.DateTimeField(null=True, blank=True)
    opt_in_end = models.DateTimeField(null=True, blank=True)
    setup_start = models.DateTimeField(null=True, blank=True)
    launched_at = models.DateTimeField(null=True, blank=True)
    expected_end_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sourcing')
    
    # Images/Documents
    cover_image = models.ImageField(upload_to='deals/covers/', null=True, blank=True)
    
    # Stats (calculated)
    total_opted_in = models.IntegerField(default=0)
    total_collected = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='deals_created')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['reference']),
        ]
    
    def __str__(self):
        return f"{self.reference}: {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Deal.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
    
    @property
    def available_slots(self):
        """Get number of available opt-in slots"""
        if self.max_opt_in_members:
            return max(0, self.max_opt_in_members - self.total_opted_in)
        return None  # Unlimited
    
    @property
    def is_opt_in_open(self):
        """Check if opt-in is currently open"""
        now = timezone.now()
        return (
            self.status == 'opt_in_open' and
            self.opt_in_start and
            self.opt_in_end and
            self.opt_in_start <= now <= self.opt_in_end
        )
    
    @property
    def progress_percentage(self):
        """Calculate funding progress percentage"""
        if self.total_capital_required > 0:
            return (self.total_collected / self.total_capital_required) * 100
        return 0
    
    @property
    def can_proceed(self):
        """Check if deal has enough opt-ins to proceed"""
        return self.total_opted_in >= self.min_opt_in_members


class DealOptIn(models.Model):
    """Member opt-in to a deal"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deal_opt_ins')
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='opt_ins')
    reference = models.CharField(max_length=50, unique=True, default=generate_uuid)
    
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'deal']  # One opt-in per user per deal
    
    def __str__(self):
        return f"{self.user.email} - {self.deal.title} - {self.amount}"
    
    def confirm(self):
        """Confirm opt-in after payment"""
        self.status = 'confirmed'
        self.paid_at = timezone.now()
        self.save()
        
        # Update deal stats
        self.deal.total_opted_in += 1
        self.deal.total_collected += self.amount
        self.deal.save()


class DealRevenue(models.Model):
    """Revenue generated by the deal"""
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='revenues')
    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=200)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-period_end']
    
    def __str__(self):
        return f"{self.deal.title} - {self.period_start} to {self.period_end}: {self.amount}"


class DealCost(models.Model):
    """Operating costs for the deal"""
    COST_TYPES = [
        ('operating', 'Operating Cost'),
        ('staff', 'Staff Salary'),
        ('rent', 'Rent/Lease'),
        ('utilities', 'Utilities'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ]
    
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='costs')
    cost_type = models.CharField(max_length=20, choices=COST_TYPES)
    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=200)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-period_end']
    
    def __str__(self):
        return f"{self.deal.title} - {self.get_cost_type_display()}: {self.amount}"


class DealProfitDistribution(models.Model):
    """Profit distribution to opted-in members"""
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='distributions')
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Financial breakdown
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2)
    total_costs = models.DecimalField(max_digits=14, decimal_places=2)
    net_profit = models.DecimalField(max_digits=14, decimal_places=2)
    
    management_fee = models.DecimalField(max_digits=14, decimal_places=2)
    performance_carry = models.DecimalField(max_digits=14, decimal_places=2)
    members_share = models.DecimalField(max_digits=14, decimal_places=2)
    
    distribution_per_member = models.DecimalField(max_digits=14, decimal_places=2)
    total_members = models.IntegerField()
    
    distributed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-period_end']
    
    def __str__(self):
        return f"{self.deal.title} - {self.period_start} to {self.period_end}"


class DealReport(models.Model):
    """Monthly reports for members"""
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='reports')
    title = models.CharField(max_length=200)
    period = models.DateField(help_text="Month/quarter of the report")
    
    # Report content
    summary = models.TextField()
    revenue_details = models.TextField(blank=True)
    cost_details = models.TextField(blank=True)
    aml_share = models.DecimalField(max_digits=14, decimal_places=2, help_text="AML management fee + carry")
    net_profit = models.DecimalField(max_digits=14, decimal_places=2)
    
    # Status
    status_update = models.CharField(max_length=100, help_text="e.g., Active, Monitoring, Closed")
    next_steps = models.TextField(blank=True)
    
    # File
    pdf_report = models.FileField(upload_to='deals/reports/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-period']
    
    def __str__(self):
        return f"{self.deal.title} - {self.title}"


class DealUpdate(models.Model):
    """Status updates for members"""
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='updates')
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_important = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.deal.title} - {self.title}"