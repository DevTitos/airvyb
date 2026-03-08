from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.views.decorators.http import require_POST, require_GET
from decimal import Decimal
import json
import logging

from .models import Deal, DealOptIn, DealCategory, DealReport, DealUpdate

logger = logging.getLogger(__name__)

# ============================================
# DEAL LISTING
# ============================================

@require_GET
def deal_list(request):
    """List all available deals"""
    category = request.GET.get('category')
    status = request.GET.get('status', 'opt_in_open')
    
    deals = Deal.objects.all()
    
    if category:
        deals = deals.filter(category_id=category)
    
    if status:
        deals = deals.filter(status=status)
    
    # Get opted-in deals for current user
    user_opt_in_deal_ids = []
    if request.user.is_authenticated:
        user_opt_in_deal_ids = list(
            DealOptIn.objects.filter(
                user=request.user,
                status='confirmed'
            ).values_list('deal_id', flat=True)
        )
    
    context = {
        'deals': deals,
        'categories': DealCategory.objects.filter(is_active=True),
        'user_opt_in_deal_ids': user_opt_in_deal_ids,  # Pass list instead of dict
        'current_category': category,
        'current_status': status,
    }
    
    return render(request, 'deals/deal_list.html', context)


# ============================================
# DEAL DETAIL
# ============================================

@require_GET
def deal_detail(request, slug):
    """Show deal details"""
    deal = get_object_or_404(Deal, slug=slug)
    
    # Check if user has opted in
    user_opt_in = None
    if request.user.is_authenticated:
        try:
            user_opt_in = DealOptIn.objects.get(
                user=request.user,
                deal=deal
            )
        except DealOptIn.DoesNotExist:
            pass
    
    # Get recent reports
    reports = deal.reports.all()[:3]
    
    # Get updates
    updates = deal.updates.all()[:5]
    
    context = {
        'deal': deal,
        'user_opt_in': user_opt_in,
        'reports': reports,
        'updates': updates,
        'can_opt_in': (
            deal.is_opt_in_open and
            not user_opt_in and
            (deal.available_slots is None or deal.available_slots > 0)
        ),
    }
    
    return render(request, 'deals/deal_detail.html', context)


# ============================================
# OPT-IN TO DEAL
# ============================================

@login_required
@require_POST
def opt_in_deal(request, deal_id):
    """Member opts in to a deal"""
    deal = get_object_or_404(Deal, id=deal_id)
    
    # Check if opt-in is open
    if not deal.is_opt_in_open:
        messages.error(request, 'Opt-in period for this deal is closed.')
        return redirect('deals:detail', slug=deal.slug)
    
    # Check if user already opted in
    if DealOptIn.objects.filter(user=request.user, deal=deal).exists():
        messages.warning(request, 'You have already opted in to this deal.')
        return redirect('deals:detail', slug=deal.slug)
    
    # Check available slots
    if deal.available_slots is not None and deal.available_slots <= 0:
        messages.error(request, 'No available slots for this deal.')
        return redirect('deals:detail', slug=deal.slug)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Create opt-in record
                opt_in = DealOptIn.objects.create(
                    user=request.user,
                    deal=deal,
                    amount=deal.opt_in_amount,
                    status='pending',
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                # For now, simulate payment success
                # In production, integrate with M-Pesa/wallet
                opt_in.confirm()
                
                messages.success(
                    request,
                    f'Successfully opted in to {deal.title}! You will receive updates as the deal progresses.'
                )
                
                return redirect('deals:detail', slug=deal.slug)
        
        except Exception as e:
            logger.error(f"Opt-in error: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred. Please try again.')
            return redirect('deals:detail', slug=deal.slug)
    
    return redirect('deals:detail', slug=deal.slug)


# ============================================
# MY DEALS (USER'S OPT-INS)
# ============================================

@login_required
@require_GET
def my_deals(request):
    """Show deals the user has opted into"""
    opt_ins = DealOptIn.objects.filter(
        user=request.user,
        status='confirmed'
    ).select_related('deal').order_by('-created_at')
    
    context = {
        'opt_ins': opt_ins,
    }
    
    return render(request, 'deals/my_deals.html', context)


# ============================================
# DEAL REPORT VIEW
# ============================================

@login_required
@require_GET
def deal_report(request, report_id):
    """View a specific deal report"""
    report = get_object_or_404(DealReport, id=report_id)
    
    # Check if user is opted in to this deal
    if not DealOptIn.objects.filter(
        user=request.user,
        deal=report.deal,
        status='confirmed'
    ).exists():
        messages.error(request, 'You must opt in to this deal to view reports.')
        return redirect('deals:detail', slug=report.deal.slug)
    
    context = {
        'report': report,
    }
    
    return render(request, 'deals/deal_report.html', context)


# ============================================
# DEAL DASHBOARD (AML Management)
# ============================================

@login_required
def aml_dashboard(request):
    """Dashboard for AML to manage deals"""
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('deals:list')
    
    deals = Deal.objects.all().order_by('-created_at')
    
    stats = {
        'total_deals': deals.count(),
        'active_deals': deals.filter(status='active').count(),
        'opt_in_open': deals.filter(status='opt_in_open').count(),
        'total_opted_in': sum(deal.total_opted_in for deal in deals),
        'total_collected': sum(deal.total_collected for deal in deals),
    }
    
    context = {
        'deals': deals,
        'stats': stats,
    }
    
    return render(request, 'deals/aml_dashboard.html', context)


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip