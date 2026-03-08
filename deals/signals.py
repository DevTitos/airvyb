from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import DealOptIn, DealRevenue, DealCost


@receiver(post_save, sender=DealOptIn)
def update_deal_on_opt_in(sender, instance, created, **kwargs):
    """Update deal totals when opt-in is confirmed"""
    if instance.status == 'confirmed' and created:
        deal = instance.deal
        deal.total_opted_in += 1
        deal.total_collected += instance.amount
        deal.save()


@receiver(post_delete, sender=DealOptIn)
def update_deal_on_opt_in_delete(sender, instance, **kwargs):
    """Update deal totals when opt-in is deleted"""
    if instance.status == 'confirmed':
        deal = instance.deal
        deal.total_opted_in = max(0, deal.total_opted_in - 1)
        deal.total_collected = max(0, deal.total_collected - instance.amount)
        deal.save()