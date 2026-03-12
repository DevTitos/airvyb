from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal
import uuid

User = get_user_model()

def generate_uuid():
    """Generate a unique ID"""
    return f"{uuid.uuid4().hex[:12].upper()}"

class DealCategory(models.Model):
    """Categories for deals"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default="briefcase")
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = "Deal Categories"
    
    def __str__(self):
        return self.name


class Deal(models.Model):
    """Deal sourced by Airvyb Management Ltd (AML) - NFT Collection"""
    
    RISK_LEVELS = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
    ]
    
    STATUS_CHOICES = [
        ('sourcing', 'Sourcing'),
        ('disclosed', 'Disclosed'),
        ('opt_in_open', 'Opt-In Open'),
        ('opt_in_closed', 'Opt-In Closed'),
        ('setup', 'Setup'),
        ('active', 'Active'),
        ('monitoring', 'Monitoring'),
        ('paused', 'Paused'),
        ('closed', 'Closed'),
        ('scaling', 'Scaling'),
    ]
    
    # Basic Info
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    category = models.ForeignKey(DealCategory, on_delete=models.SET_NULL, null=True, related_name='deals')
    reference = models.CharField(max_length=50, unique=True, default=generate_uuid)
    
    # Deal Details
    objective = models.TextField()
    description = models.TextField()
    
    # Financials
    opt_in_amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    total_capital_required = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    min_opt_in_members = models.IntegerField(default=1)
    max_opt_in_members = models.IntegerField(null=True, blank=True)
    
    # Operations
    expected_operations = models.TextField()
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS, default='medium')
    duration_months = models.IntegerField(validators=[MinValueValidator(1)])
    
    # Management Fees
    management_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=10.00
    )
    performance_carry_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=20.00
    )
    
    # Timeline
    disclosed_at = models.DateTimeField(null=True, blank=True)
    opt_in_start = models.DateTimeField(null=True, blank=True)
    opt_in_end = models.DateTimeField(null=True, blank=True)
    launched_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sourcing')
    
    # Images
    cover_image = models.ImageField(upload_to='deals/covers/', null=True, blank=True)
    
    # Stats (calculated)
    total_opted_in = models.IntegerField(default=0)
    total_collected = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    # Hedera NFT Collection Fields
    hedera_token_id = models.CharField(max_length=50, null=True, blank=True, unique=True,
                                       help_text="Hedera Token ID for this NFT collection")
    hedera_topic_id = models.CharField(max_length=50, null=True, blank=True,
                                      help_text="Hedera topic for deal updates")
    hedera_metadata_uri = models.URLField(max_length=500, null=True, blank=True,
                                         help_text="URI to collection metadata on IPFS")
    hedera_supply_key_encrypted = models.TextField(null=True, blank=True,
                                                  help_text="Encrypted supply key for minting NFTs")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='deals_created')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['reference']),
            models.Index(fields=['hedera_token_id']),
        ]
    
    def __str__(self):
        return f"{self.reference}: {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
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
        if self.max_opt_in_members:
            return max(0, self.max_opt_in_members - self.total_opted_in)
        return None
    
    @property
    def is_opt_in_open(self):
        now = timezone.now()
        return (
            self.status == 'opt_in_open' and
            self.opt_in_start and
            self.opt_in_end and
            self.opt_in_start <= now <= self.opt_in_end
        )
    
    @property
    def progress_percentage(self):
        if self.total_capital_required > 0:
            return (self.total_collected / self.total_capital_required) * 100
        return 0
    
    @property
    def hedera_explorer_url(self):
        if self.hedera_token_id:
            return f"https://hashscan.io/testnet/token/{self.hedera_token_id}"
        return None


class DealOptIn(models.Model):
    """Member opt-in to a deal - NFT minting proof"""
    
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
    transaction = models.ForeignKey('finance.Transaction', on_delete=models.SET_NULL, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Hedera NFT Fields - Proof of opt-in
    hedera_serial_number = models.IntegerField(null=True, blank=True,
                                               help_text="NFT serial number for this opt-in")
    hedera_nft_id = models.CharField(max_length=100, null=True, blank=True,
                                     help_text="Full NFT ID (token_id/serial)")
    hedera_message_id = models.CharField(max_length=100, null=True, blank=True,
                                        help_text="Hedera message ID for NFT minting")
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'deal']  # One opt-in per user per deal
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['hedera_nft_id']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.deal.title}"
    
    def confirm(self):
        """Confirm opt-in after payment"""
        self.status = 'confirmed'
        self.paid_at = timezone.now()
        self.save()
        
        # Update deal stats
        self.deal.total_opted_in += 1
        self.deal.total_collected += self.amount
        self.deal.save()
    
    @property
    def hedera_explorer_url(self):
        if self.hedera_nft_id:
            return f"https://hashscan.io/testnet/token/{self.hedera_nft_id}"
        return None


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
        return f"{self.deal.title} - {self.period_start}: {self.amount}"


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
    
    # Hedera distribution tracking
    distribution_topic_id = models.CharField(max_length=50, null=True, blank=True,
                                            help_text="Hedera topic for distribution record")
    
    class Meta:
        ordering = ['-period_end']
    
    def __str__(self):
        return f"{self.deal.title} - {self.period_start}"


class DealReport(models.Model):
    """Monthly reports for members"""
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='reports')
    title = models.CharField(max_length=200)
    period = models.DateField()
    
    summary = models.TextField()
    revenue_details = models.TextField(blank=True)
    cost_details = models.TextField(blank=True)
    aml_share = models.DecimalField(max_digits=14, decimal_places=2)
    net_profit = models.DecimalField(max_digits=14, decimal_places=2)
    
    status_update = models.CharField(max_length=100)
    next_steps = models.TextField(blank=True)
    
    pdf_report = models.FileField(upload_to='deals/reports/', null=True, blank=True)
    
    # Hedera report record
    hedera_message_id = models.CharField(max_length=100, null=True, blank=True)
    
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
    
    # Hedera update record
    hedera_message_id = models.CharField(max_length=100, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.deal.title} - {self.title}"