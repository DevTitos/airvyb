from django.db import models
from django.db.models import Sum, Count, Q
from django.utils import timezone

class VentureManager(models.Manager):
    def active(self):
        return self.filter(status='active')
    
    def open_for_investment(self):
        return self.filter(
            status='active',
            shares_available__gt=models.F('shares_issued')
        )
    
    def by_type(self, venture_type):
        return self.filter(venture_type=venture_type)
    
    def high_performing(self):
        # Ventures with high percentage funded
        return self.filter(
            status='active'
        ).annotate(
            funded_percentage=(models.F('shares_issued') * 100) / models.F('shares_available')
        ).filter(
            funded_percentage__gt=70
        ).order_by('-funded_percentage')

class InvestmentManager(models.Manager):
    def active(self):
        return self.filter(status__in=['confirmed', 'active'])
    
    def by_user(self, user):
        return self.filter(investor=user)
    
    def recent(self, days=30):
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.filter(invested_at__gte=cutoff_date)
    
    def profitable(self):
        # Investments with positive returns
        return self.filter(
            status__in=['confirmed', 'active', 'matured'],
            dividend__amount__gt=0
        ).distinct()

class TransactionManager(models.Manager):
    def successful(self):
        return self.filter(status='completed')
    
    def by_type(self, transaction_type):
        return self.filter(transaction_type=transaction_type)
    
    def recent_by_user(self, user, limit=10):
        return self.filter(user=user).order_by('-created_at')[:limit]
    
    def total_amount_by_period(self, start_date, end_date, transaction_type=None):
        queryset = self.filter(
            created_at__range=[start_date, end_date],
            status='completed'
        )
        
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        return queryset.aggregate(total=Sum('amount'))['total'] or 0