from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Investment, UserPortfolio, Venture

User = get_user_model()

@receiver(post_save, sender=Investment)
def update_portfolio_on_investment(sender, instance, created, **kwargs):
    """Update user portfolio when investment changes"""
    if instance.investor:
        portfolio, created = UserPortfolio.objects.get_or_create(user=instance.investor)
        portfolio.update_portfolio()

@receiver(post_save, sender=Venture)
def update_investments_on_venture_change(sender, instance, **kwargs):
    """Update related investments when venture changes"""
    # Update current value calculations for all investments in this venture
    for investment in instance.investments.all():
        # Trigger portfolio update
        if investment.investor:
            portfolio, created = UserPortfolio.objects.get_or_create(user=investment.investor)
            portfolio.update_portfolio()

@receiver(post_save, sender=User)
def create_user_portfolio(sender, instance, created, **kwargs):
    """Create portfolio when user is created"""
    if created:
        UserPortfolio.objects.create(user=instance)