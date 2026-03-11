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
import string
import random

from .models import Deal, DealOptIn, DealCategory, DealReport, DealUpdate
from finance.models import Wallet, Transaction
from finance.hcs import submit_message as submit_hcs_transaction
from hiero.nft import create_nft, mint_nft, associate_nft

logger = logging.getLogger(__name__)

# ============================================
# DEAL LISTING
# ============================================

def id_generator(size=12, chars=string.ascii_uppercase + string.digits):
    """Generate random reference ID"""
    return ''.join(random.choice(chars) for _ in range(size))

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

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
    
    # Check Wallet Balance
    wallet = Wallet.objects.get(user=request.user)
    bal = wallet.balance
    if bal < deal.opt_in_amount:
        messages.error(request, f'You do not have sufficient Funds in your Account to opt in to this deal, please add funds and try again.')
        return redirect('deals:detail', slug=deal.slug)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Deduct Payment amount from Wallet
                wallet.balance -= deal.opt_in_amount
                wallet.save()

                # Create Transaction Record on db and hcs
                reference = f"OPTIN-{timezone.now().strftime('%Y%m%d%H%M%S')}-{request.user.id}-{id_generator(6)}"
                Transaction.objects.create(
                    user=request.user,
                    transaction_type='deposit',
                    payment_method='mpesa',
                    reference=reference,
                    amount=deal.opt_in_amount,
                    fee=0,
                    net_amount=deal.opt_in_amount,
                    balance_before=wallet.balance + deal.opt_in_amount,
                    balance_after=wallet.balance,
                    phone_number=request.user.phone_number,
                    description=f"Deal opt in of KES {deal.opt_in_amount:,.0f} from {request.user.phone_number}",
                    status='completed',
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    initiated_at=timezone.now(),
                    metadata={
                        'payment_gateway': 'intasend',
                        'provider': 'm-pesa',
                        'external_reference': reference,
                        'initiation_source': 'web'
                    }
                )
                # Create opt-in record
                opt_in = DealOptIn.objects.create(
                    user=request.user,
                    deal=deal,
                    amount=deal.opt_in_amount,
                    status='confirmed',
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
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


# CREATE DEAL
@login_required
def aml_createDeal(request):
    """Dashboard for AML to manage deals"""
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('deals:list')
    
    # Handle Deal POST

    # Handle NFT Creation
    receipt = create_nft(title="deal Title", symbol="NFTSYMBOL", max_supply=100)
    
    return render(request, 'deals/aml_dashboard.html')