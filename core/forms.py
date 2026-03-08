from django import forms
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Venture, Investment

class VentureFilterForm(forms.Form):
    """Filter ventures form"""
    venture_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Venture.VENTURE_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Venture.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    min_investment = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min amount'
        })
    )
    
    sort_by = forms.ChoiceField(
        choices=[
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
            ('funding', 'Most Funded'),
            ('lowest_investment', 'Lowest Minimum'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class InvestmentForm(forms.ModelForm):
    """Create investment form"""
    class Meta:
        model = Investment
        fields = ['shares']
        widgets = {
            'shares': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Number of shares'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.venture = kwargs.pop('venture', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.venture:
            # Set max shares based on venture availability
            max_shares = self.venture.available_shares
            self.fields['shares'].validators.append(
                forms.ValidationError(f"Maximum {max_shares} shares available")
            )
    
    def clean_shares(self):
        shares = self.cleaned_data.get('shares')
        
        if not self.venture:
            raise ValidationError('Venture not specified')
        
        if shares > self.venture.available_shares:
            raise ValidationError(f'Only {self.venture.available_shares} shares available')
        
        if shares * self.venture.price_per_share < self.venture.minimum_investment:
            raise ValidationError(
                f'Minimum investment is Ksh {self.venture.minimum_investment}'
            )
        
        return shares
    
    def save(self, commit=True):
        investment = super().save(commit=False)
        investment.venture = self.venture
        investment.investor = self.user
        investment.share_price_at_purchase = self.venture.price_per_share
        investment.amount_invested = self.cleaned_data['shares'] * self.venture.price_per_share
        
        if commit:
            investment.save()
        return investment

class QuickInvestmentForm(forms.Form):
    """Quick investment with amount (not shares)"""
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('500.00'))],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Investment amount (Ksh)'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.venture = kwargs.pop('venture', None)
        super().__init__(*args, **kwargs)
        
        if self.venture:
            self.fields['amount'].validators.append(
                MinValueValidator(self.venture.minimum_investment)
            )
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        
        if not self.venture:
            raise ValidationError('Venture not specified')
        
        # Calculate shares
        shares = int(amount / self.venture.price_per_share)
        
        if shares == 0:
            raise ValidationError(f'Amount too low. Minimum is Ksh {self.venture.minimum_investment}')
        
        if shares > self.venture.available_shares:
            max_amount = self.venture.available_shares * self.venture.price_per_share
            raise ValidationError(f'Maximum investment is Ksh {max_amount:.2f}')
        
        return amount
    
    def create_investment(self, user):
        amount = self.cleaned_data['amount']
        venture = self.venture
        
        shares = int(amount / venture.price_per_share)
        actual_amount = shares * venture.price_per_share
        
        return Investment.objects.create(
            investor=user,
            venture=venture,
            shares=shares,
            amount_invested=actual_amount,
            share_price_at_purchase=venture.price_per_share,
            status='pending'
        )