from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
from decimal import Decimal
from core.models import Investment, Dividend

User = get_user_model()

def generate_uuid():
    return f"{uuid.uuid4().hex[:8].upper()}"

class Wallet(models.Model):
    """User wallet for managing funds"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    
    # Balances
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    locked_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    total_deposited = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    # Limits
    daily_deposit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=150000)
    daily_withdrawal_limit = models.DecimalField(max_digits=14, decimal_places=2, default=150000)
    remaining_daily_deposit = models.DecimalField(max_digits=14, decimal_places=2, default=150000)
    remaining_daily_withdrawal = models.DecimalField(max_digits=14, decimal_places=2, default=150000)
    
    # Timestamps
    last_deposit_at = models.DateTimeField(null=True, blank=True)
    last_withdrawal_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - Balance: {self.balance}"
    
    @property
    def available_balance(self):
        """Balance available for withdrawal"""
        return self.balance - self.locked_balance


class Loan(models.Model):
    """User loans/borrowing"""
    LOAN_PURPOSES = [
        ('investment', 'Venture Investment'),
        ('personal', 'Personal'),
        ('business', 'Business'),
        ('emergency', 'Emergency'),
        ('education', 'Education'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('repaid', 'Fully Repaid'),
        ('defaulted', 'Defaulted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    REPAYMENT_FREQUENCY = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('lump_sum', 'Lump Sum'),
    ]
    
    # Basic Info
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    reference = models.CharField(max_length=50, unique=True, default=generate_uuid)
    purpose = models.CharField(max_length=20, choices=LOAN_PURPOSES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Loan Details
    amount_requested = models.DecimalField(max_digits=14, decimal_places=2)
    amount_approved = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    tenure_months = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(60)])
    repayment_frequency = models.CharField(max_length=20, choices=REPAYMENT_FREQUENCY, default='monthly')
    
    # Financial Calculations
    total_repayable = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    outstanding_balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    
    # Credit Assessment
    credit_score = models.IntegerField(null=True, blank=True)
    assessment_notes = models.TextField(blank=True)
    
    # Related
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_loans')
    investment = models.ForeignKey(Investment, on_delete=models.SET_NULL, null=True, blank=True, related_name='loans')
    
    # Dates
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    first_payment_date = models.DateField(null=True, blank=True)
    expected_repayment_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-applied_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['reference']),
        ]
    
    def __str__(self):
        return f"{self.reference}: {self.user.email} - {self.amount_requested}"
    
    def calculate_repayment(self):
        """Calculate total repayable amount"""
        interest = self.amount_approved * (self.interest_rate / Decimal('100')) * (self.tenure_months / Decimal('12'))
        self.total_repayable = self.amount_approved + interest
        self.outstanding_balance = self.total_repayable - self.amount_paid
        return self.total_repayable
    
    @property
    def progress_percentage(self):
        if not self.total_repayable:
            return 0
        return (self.amount_paid / self.total_repayable) * 100
    
    @property
    def monthly_installment(self):
        if self.repayment_frequency == 'monthly' and self.tenure_months > 0:
            return self.total_repayable / self.tenure_months
        return 0

class Transaction(models.Model):
    """All financial transactions"""
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('investment', 'Investment'),
        ('dividend', 'Dividend Payment'),
        ('loan', 'Loan Disbursement'),
        ('loan_repayment', 'Loan Repayment'),
        ('fee', 'Fee'),
        ('refund', 'Refund'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHODS = [
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
        ('card', 'Credit/Debit Card'),
        ('wallet', 'Wallet Balance'),
    ]
    
    # Basic Info
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='transactions'  # Use plural for consistency
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='mpesa', blank=True)
    reference = models.CharField(max_length=50, unique=True, default=generate_uuid)
    
    # Financial Details
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    balance_before = models.DecimalField(max_digits=14, decimal_places=2)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    
    # Related Objects
    investment = models.ForeignKey(
        Investment, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='transactions'
    )
    dividend = models.ForeignKey(
        Dividend, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='transactions'
    )
    loan = models.ForeignKey(
        Loan, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='transactions'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment Details
    phone_number = models.CharField(max_length=15, blank=True)
    mpesa_code = models.CharField(max_length=50, blank=True)
    bank_account = models.CharField(max_length=100, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    
    # Metadata
    description = models.TextField()
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Dates
    initiated_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)  # Kept for backward compatibility
    
    class Meta:
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['transaction_type', 'initiated_at']),
            models.Index(fields=['reference']),
            models.Index(fields=['mpesa_code']),
            models.Index(fields=['created_at']),  # Additional index for backward compatibility
        ]
    
    def __str__(self):
        return f"{self.reference}: {self.user.email} - {self.amount} - {self.status}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate net_amount if not set
        if not self.net_amount and self.amount is not None:
            self.net_amount = self.amount - (self.fee or 0)
        
        # Ensure created_at is set for backward compatibility
        if not self.created_at and self.initiated_at:
            self.created_at = self.initiated_at
            
        super().save(*args, **kwargs)
    
    @property
    def is_debit(self):
        """Check if transaction is a debit (money out)"""
        return self.transaction_type in ['withdrawal', 'investment', 'fee', 'loan_repayment']
    
    @property
    def is_credit(self):
        """Check if transaction is a credit (money in)"""
        return self.transaction_type in ['deposit', 'dividend', 'loan', 'refund']
    
    @property
    def display_amount(self):
        """Display amount with sign"""
        if self.is_debit:
            return f"- Ksh {self.amount:,.0f}"
        else:
            return f"+ Ksh {self.amount:,.0f}"
    
    @property
    def age(self):
        """Time since transaction was initiated"""
        from django.utils import timezone
        delta = timezone.now() - self.initiated_at
        return delta

class LoanRepayment(models.Model):
    """Individual loan repayments"""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='loan_repayment')
    
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    principal_paid = models.DecimalField(max_digits=14, decimal_places=2)
    interest_paid = models.DecimalField(max_digits=14, decimal_places=2)
    
    due_date = models.DateField()
    paid_at = models.DateTimeField()
    
    class Meta:
        ordering = ['due_date']
    
    def __str__(self):
        return f"{self.loan.reference} - Payment: {self.amount}"


class PaymentMethod(models.Model):
    """Saved payment methods for users"""
    METHOD_TYPES = [
        ('mpesa', 'M-Pesa'),
        ('bank_account', 'Bank Account'),
        ('card', 'Card'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods')
    method_type = models.CharField(max_length=20, choices=METHOD_TYPES)
    
    # M-Pesa
    phone_number = models.CharField(max_length=15, blank=True)
    
    # Bank Account
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    account_name = models.CharField(max_length=100, blank=True)
    
    # Card (encrypted in production)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=20, blank=True)
    expiry_month = models.CharField(max_length=2, blank=True)
    expiry_year = models.CharField(max_length=4, blank=True)
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        if self.method_type == 'mpesa':
            return f"M-Pesa: {self.phone_number}"
        elif self.method_type == 'bank_account':
            return f"{self.bank_name}: {self.account_number}"
        else:
            return f"{self.card_brand}: ****{self.card_last4}"


class FinanceSummary(models.Model):
    """User finance summary for dashboard"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='finance_summary')
    
    # Totals
    total_deposits = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_withdrawals = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_invested = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_dividends = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    # Loans
    total_loans_taken = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_loans_repaid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    active_loans_count = models.IntegerField(default=0)
    total_interest_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    # Fees
    total_fees_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    # Limits
    daily_deposit_used = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    daily_withdrawal_used = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    last_calculated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Finance Summary: {self.user.email}"
    
    def calculate_summary(self):
        """Recalculate all financial summaries"""
        from django.db.models import Sum
        
        # Calculate transactions
        completed_transactions = Transaction.objects.filter(
            user=self.user,
            status='completed'
        )
        
        self.total_deposits = completed_transactions.filter(
            transaction_type='deposit'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        self.total_withdrawals = completed_transactions.filter(
            transaction_type='withdrawal'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        self.total_invested = completed_transactions.filter(
            transaction_type='investment'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        self.total_dividends = completed_transactions.filter(
            transaction_type='dividend'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        self.total_fees_paid = completed_transactions.aggregate(
            Sum('fee')
        )['fee__sum'] or 0
        
        # Calculate loans
        active_loans = Loan.objects.filter(
            user=self.user,
            status__in=['active', 'approved']
        )
        
        self.active_loans_count = active_loans.count()
        
        loan_aggregates = active_loans.aggregate(
            total_loans_taken=Sum('amount_approved'),
            total_loans_repaid=Sum('amount_paid')
        )
        
        self.total_loans_taken = loan_aggregates['total_loans_taken'] or 0
        self.total_loans_repaid = loan_aggregates['total_loans_repaid'] or 0
        
        self.save()