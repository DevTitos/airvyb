from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import json
from django.db import models
from django.db.models import Prefetch, OuterRef, Subquery, Exists, Count, Sum, F, Q
from .models import (
    Venture, Investment, Dividend,
    UserPortfolio, Notification, AuditLog
)
from .forms import VentureFilterForm, InvestmentForm, QuickInvestmentForm
from .utils import log_audit, send_notification, create_transaction

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect
import requests
import string
import random, uuid
from django.contrib import messages
from django.urls import reverse
from decimal import Decimal
import json
from django.db import transaction as db_transaction
from django.views.decorators.http import require_GET
from .utils import generate_transaction_reference
from django.core.cache import cache
from finance.models import (
    Wallet, Transaction, FinanceSummary
)
from deals.models import Deal, DealOptIn, DealReport, DealUpdate

def id_generator(size=8, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def generate_transaction_reference():
    """Generate a unique transaction reference"""
    return f"INV-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

@login_required
@require_GET
def dashboard(request):
    """Main dashboard - Deals, Users & Finance focused"""
    user = request.user
    cache_key = f'dashboard_{user.id}'
    
    # Try to get cached dashboard data
    cached_context = cache.get(cache_key)
    if cached_context:
        return render(request, 'dashboard.html', cached_context)
    
    # ============================================
    # USER PORTFOLIO & FINANCE DATA
    # ============================================
    
    # Get or create portfolio (single query)
    portfolio, created = UserPortfolio.objects.get_or_create(user=user)
    
    # Async portfolio update check
    if not created:
        time_threshold = timezone.now() - timezone.timedelta(hours=1)
        if portfolio.last_updated < time_threshold:
            # Trigger async update (Celery task)
            # update_portfolio.delay(user.id)
            pass
    
    # Get wallet balance
    try:
        wallet = Wallet.objects.get(user=user)
        wallet_balance = wallet.balance
        available_balance = wallet.available_balance
    except Wallet.DoesNotExist:
        wallet_balance = 0
        available_balance = 0
    
    # Get finance summary
    try:
        finance_summary = FinanceSummary.objects.get(user=user)
    except FinanceSummary.DoesNotExist:
        finance_summary = None
    
    # Recent transactions (last 5)
    recent_transactions = Transaction.objects.filter(
        user=user
    ).select_related(
        'investment__venture'
    ).only(
        'id', 'reference', 'transaction_type', 'amount', 
        'status', 'description', 'created_at',
        'investment__venture__name'
    ).order_by('-created_at')[:5]
    
    # Dashboard stats
    dashboard_stats = Investment.objects.filter(
        investor=user
    ).aggregate(
        total_investments=Count('id'),
        active_investments=Count('id', filter=Q(status__in=['confirmed', 'active'])),
        total_invested=Sum('amount_invested'),
    )
    
    # Calculate total dividends
    total_dividends = Dividend.objects.filter(
        investment__investor=user,
        status='paid'
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # ============================================
    # DEALS DATA (Member Opt-Ins)
    # ============================================
    
    # Deals the user has opted into
    my_opted_deals = DealOptIn.objects.filter(
        user=user,
        status='confirmed'
    ).select_related(
        'deal', 'deal__category'
    ).order_by('-created_at')[:5]
    
    # Count of deals by status
    deals_count = {
        'opted_in': DealOptIn.objects.filter(user=user, status='confirmed').count(),
        'pending': DealOptIn.objects.filter(user=user, status='pending').count(),
    }
    
    # Open deals available for opt-in (excluding those user already opted into)
    opted_deal_ids = DealOptIn.objects.filter(
        user=user
    ).values_list('deal_id', flat=True)
    
    open_deals = Deal.objects.filter(
        status='opt_in_open',
        opt_in_end__gte=timezone.now()
    ).exclude(
        id__in=opted_deal_ids
    ).select_related('category').only(
        'id', 'title', 'slug', 'objective', 'opt_in_amount',
        'risk_level', 'duration_months', 'total_opted_in',
        'max_opt_in_members', 'category__name', 'category__icon'
    ).order_by('-created_at')[:3]
    
    # Recent deal updates for opted-in deals
    recent_updates = DealUpdate.objects.filter(
        deal__opt_ins__user=user,
        deal__opt_ins__status='confirmed'
    ).select_related('deal').order_by('-created_at')[:5]
    
    # Deal performance summary
    deal_performance = {
        'total_opted_in': DealOptIn.objects.filter(
            user=user, status='confirmed'
        ).count(),
        'active_deals': Deal.objects.filter(
            opt_ins__user=user,
            opt_ins__status='confirmed',
            status__in=['active', 'monitoring']
        ).distinct().count(),
        'total_invested_in_deals': DealOptIn.objects.filter(
            user=user, status='confirmed'
        ).aggregate(total=Sum('amount'))['total'] or 0,
    }
    
    # ============================================
    # NOTIFICATIONS
    # ============================================
    
    notifications = Notification.objects.filter(
        user=user,
        is_read=False
    ).only(
        'id', 'title', 'message', 'notification_type', 
        'created_at', 'is_important'
    ).order_by('-created_at', '-is_important')[:5]
    
    # ============================================
    # CONTEXT ASSEMBLY
    # ============================================
    
    context = {
        # User Info
        'user_name': user.get_full_name() or user.email.split('@')[0],
        'user_email': user.email,
        
        # Portfolio & Finance
        'portfolio': portfolio,
        'wallet_balance': wallet_balance,
        'available_balance': available_balance,
        'finance_summary': finance_summary,
        'recent_transactions': recent_transactions,
        'dashboard_stats': dashboard_stats,
        'total_dividends': total_dividends,
        
        # Deals
        'my_opted_deals': my_opted_deals,
        'deals_count': deals_count,
        'open_deals': open_deals,
        'recent_updates': recent_updates,
        'deal_performance': deal_performance,
        
        # Notifications
        'notifications': notifications,
        'has_notifications': notifications.exists(),
        
        # Cache
        'cache_timeout': 300,
    }
    
    # Cache the context for 5 minutes
    cache.set(cache_key, context, 300)
    
    return render(request, 'dashboard.html', context)


@login_required
def portfolio_detail(request):
    """Detailed portfolio view"""
    user = request.user
    # Get user portfolio
    portfolio, created = UserPortfolio.objects.get_or_create(user=user)
    portfolio.update_portfolio()
    
    # Get active investments
    active_investments = Investment.objects.filter(
        investor=user,
        status__in=['confirmed', 'active']
    ).select_related('venture')
    
    # Get recent transactions
    recent_transactions = Transaction.objects.filter(
        user=user
    ).order_by('-created_at')[:10]
    
    # Calculate allocation data
    allocation_data = []
    
    
    context = {
        'portfolio': portfolio,
        'active_investments': active_investments,
        'recent_transactions': recent_transactions,
        'allocation_data': allocation_data,
    }
    
    return render(request, 'core/portfolio.html', context)

# Venture Views
def venture_list(request):
    """List all available ventures"""
    ventures = Venture.objects.filter(status='active')
    
    # Apply filters
    form = VentureFilterForm(request.GET)
    if form.is_valid():
        venture_type = form.cleaned_data.get('venture_type')
        status = form.cleaned_data.get('status')
        min_investment = form.cleaned_data.get('min_investment')
        sort_by = form.cleaned_data.get('sort_by')
        
        if venture_type:
            ventures = ventures.filter(venture_type=venture_type)
        
        if status:
            ventures = ventures.filter(status=status)
        
        if min_investment:
            ventures = ventures.filter(minimum_investment__gte=min_investment)
        
        # Apply sorting
        if sort_by == 'newest':
            ventures = ventures.order_by('-created_at')
        elif sort_by == 'oldest':
            ventures = ventures.order_by('created_at')
        elif sort_by == 'funding':
            ventures = ventures.annotate(
                funded_percentage=(models.F('shares_issued') * 100) / models.F('shares_available')
            ).order_by('-funded_percentage')
        elif sort_by == 'lowest_investment':
            ventures = ventures.order_by('minimum_investment')
    
    # Pagination
    paginator = Paginator(ventures, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'ventures': page_obj,
        'filter_form': form,
    }
    
    return render(request, 'core/venture_list.html', context)

def venture_detail(request, venture_id):
    """Venture detail view"""
    venture = get_object_or_404(Venture, id=venture_id)
    
    # Get similar ventures
    similar_ventures = Venture.objects.filter(
        venture_type=venture.venture_type,
        status='active'
    ).exclude(id=venture.id)[:3]
    
    # Get recent investors
    recent_investments = venture.investments.filter(
        status__in=['confirmed', 'active']
    ).select_related('investor').order_by('-invested_at')[:5]
    
    # Check if user has invested
    user_has_invested = False
    user_investment = None
    
    if request.user.is_authenticated:
        user_has_invested = venture.investments.filter(
            investor=request.user,
            status__in=['confirmed', 'active']
        ).exists()
        
        if user_has_invested:
            user_investment = venture.investments.filter(
                investor=request.user
            ).first()
    
    context = {
        'venture': venture,
        'similar_ventures': similar_ventures,
        'recent_investments': recent_investments,
        'user_has_invested': user_has_invested,
        'user_investment': user_investment,
    }
    
    return render(request, 'core/venture_detail.html', context)

# Investment Views
@login_required
@require_http_methods(['GET', 'POST'])
def invest(request, venture_id):
    """Make an investment"""
    venture = get_object_or_404(Venture, id=venture_id)
    
    if not venture.is_open_for_investment:
        return JsonResponse({
            'success': False,
            'message': 'This venture is not open for investment'
        }, status=400)
    
    if request.method == 'POST':
        form = QuickInvestmentForm(request.POST, venture=venture)
        
        if form.is_valid():
            with transaction.atomic():
                # Create investment
                investment = form.create_investment(request.user)
                
                # Create transaction record
                txn = create_transaction(
                    user=request.user,
                    amount=investment.amount_invested,
                    transaction_type='investment',
                    investment=investment,
                    description=f"Investment in {venture.name}",
                    metadata={'venture_id': venture.id, 'shares': investment.shares}
                )
                
                # Log audit
                log_audit(
                    user=request.user,
                    action='investment',
                    model_name='Investment',
                    object_id=investment.id,
                    details={
                        'venture': venture.name,
                        'amount': str(investment.amount_invested),
                        'shares': investment.shares
                    }
                )
                
                # Send notification
                send_notification(
                    user=request.user,
                    title="Investment Pending",
                    message=f"Your investment of Ksh {investment.amount_invested} in {venture.name} is pending confirmation.",
                    notification_type='investment',
                    investment=investment
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Investment created successfully!',
                    'investment_id': investment.id,
                    'redirect_url': f'/investments/{investment.id}/'
                })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
    
    # GET request - show form
    return render(request, 'core/invest.html', {'venture': venture})

@login_required
def investment_detail(request, investment_id):
    """Investment detail view"""
    investment = get_object_or_404(Investment, id=investment_id, investor=request.user)
    
    # Get related transactions
    transactions = Transaction.objects.filter(
        investment=investment
    ).order_by('-created_at')
    
    # Get dividends
    dividends = Dividend.objects.filter(
        investment=investment
    ).order_by('-payment_date')
    
    context = {
        'investment': investment,
        'transactions': transactions,
        'dividends': dividends,
    }
    
    return render(request, 'core/investment_detail.html', context)

# AJAX Views
@login_required
@csrf_exempt
@require_POST
def ajax_get_venture_stats(request, venture_id):
    """Get venture statistics for AJAX"""
    venture = get_object_or_404(Venture, id=venture_id)
    
    stats = {
        'total_value': float(venture.total_value),
        'available_shares': venture.available_shares,
        'percentage_funded': float(venture.percentage_funded),
        'price_per_share': float(venture.price_per_share),
        'minimum_investment': float(venture.minimum_investment),
        'is_open': venture.is_open_for_investment,
    }
    
    return JsonResponse({'success': True, 'stats': stats})

@login_required
@csrf_exempt
@require_POST
def ajax_calculate_investment(request):
    """Calculate investment details"""
    data = json.loads(request.body)
    venture_id = data.get('venture_id')
    amount = Decimal(data.get('amount', 0))
    
    venture = get_object_or_404(Venture, id=venture_id)
    
    if not venture.is_open_for_investment:
        return JsonResponse({
            'success': False,
            'message': 'Venture not open for investment'
        })
    
    if amount < venture.minimum_investment:
        return JsonResponse({
            'success': False,
            'message': f'Minimum investment is Ksh {venture.minimum_investment}'
        })
    
    # Calculate shares
    shares = int(amount / venture.price_per_share)
    actual_amount = shares * venture.price_per_share
    
    if shares > venture.available_shares:
        max_amount = venture.available_shares * venture.price_per_share
        return JsonResponse({
            'success': False,
            'message': f'Maximum investment is Ksh {max_amount:.2f}'
        })
    
    return JsonResponse({
        'success': True,
        'shares': shares,
        'actual_amount': float(actual_amount),
        'price_per_share': float(venture.price_per_share),
        'estimated_yearly_return': float(actual_amount * Decimal('0.15')),  # Example 15% return
    })

@login_required
@csrf_exempt
def ajax_get_portfolio_summary(request):
    """Get portfolio summary for AJAX"""
    user = request.user
    portfolio, created = UserPortfolio.objects.get_or_create(user=user)
    portfolio.update_portfolio()
    
    summary = {
        'total_invested': float(portfolio.total_invested),
        'current_value': float(portfolio.current_value),
        'total_dividends': float(portfolio.total_dividends),
        'total_gain': float(portfolio.current_value - portfolio.total_invested + portfolio.total_dividends),
        'average_return': float(portfolio.average_return),
        'active_investments': portfolio.active_investments,
        'total_investments': portfolio.total_investments,
    }
    
    return JsonResponse({'success': True, 'summary': summary})

# Transaction History
@login_required
def transaction_history(request):
    """User transaction history"""
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by type if provided
    transaction_type = request.GET.get('type')
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    # Pagination
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'transactions': page_obj,
        'transaction_type': transaction_type,
    }
    
    return render(request, 'core/transactions.html', context)

# Notifications
@login_required
def notifications(request):
    """User notifications"""
    notifications_list = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Mark as read if requested
    if request.GET.get('mark_read') == 'all':
        notifications_list.update(is_read=True)
        return redirect('notifications')
    
    # Pagination
    paginator = Paginator(notifications_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'notifications': page_obj,
    }
    
    return render(request, 'core/notifications.html', context)

@login_required
@csrf_exempt
@require_POST
def ajax_mark_notification_read(request, notification_id):
    """Mark notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    
    return JsonResponse({'success': True})

@csrf_exempt
def depositSuccess(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            response_data = data.get('response', {})
            reference = response_data.get("ExternalReference")
            status = response_data.get("Status")
            payment =  Transaction.objects.get(reference=reference)
            if status == "Success":
                payment.status = "Completed"
                payment.save()
            else:
                payment.status = "Cancelled"
                payment.save()
        except Exception as e:
            print(e)



@login_required(login_url="login")
def pay_mpesa(request):
    user = request.user
    if request.method == "POST":
        tel = request.POST['tel']
        amount = request.POST['amount']
        
        if tel and amount:
            reference = id_generator()
            ua = {
                'Content-Type': 'application/json',
                'Authorization':'Basic WDFkN3VBYVYzTUxsYjI1VmNhS2U6UHBEMlFnVkMxUXJOalNWTWU4bHhXejd6RFVNNWwzcldnQlcwZkR6cQ==',
            }
            url = 'https://backend.payhero.co.ke/api/v2/payments'
            
            data = {
                "amount": int(amount),
                "phone_number": f"{tel}",
                "channel_id": 947, 
                "provider": "m-pesa",
                "external_reference": f"{reference}",
                "callback_url": "https://airvyb.co.ke/payment/mpesa/success/"
            }
            
            try:
                res = requests.post(url=url, json=data, headers=ua)
                js = res.json()
                
                if js['success'] == True:
                    # Create deposit transaction
                    current_balance = user.wallet.balance if hasattr(user, 'wallet') else Decimal('0.00')
                    
                    Transaction.objects.create(
                        user=user,
                        transaction_type='deposit',
                        amount=Decimal(amount),
                        balance_before=current_balance,
                        balance_after=current_balance + Decimal(amount),
                        description=f"M-Pesa deposit via phone {tel}",
                        metadata={
                            'phone': tel,
                            'payment_reference': reference,
                            'payment_gateway': 'mpesa',
                            'response': js
                        },
                        reference=reference,
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )
                    
                    messages.success(request, f"STK push initiated successfully! Check your phone to complete payment.")
                else:
                    messages.warning(request, "Payment failed. Please try again.")
                    
            except Exception as e:
                messages.warning(request, f"An error occurred: {str(e)}")
        else:
            messages.warning(request, "All fields are required!")
    
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required(login_url="login")
def withdraw_funds(request):
    user = request.user
    if request.method == "POST":
        phone = request.POST.get('phone')
        amount = request.POST.get('amount')
        
        if phone and amount:
            try:
                amount_decimal = Decimal(amount)
                
                # Check user balance
                current_balance = user.wallet.balance if hasattr(user, 'wallet') else Decimal('0.00')
                
                if amount_decimal > current_balance:
                    messages.error(request, "Insufficient balance!")
                    return redirect('dashboard')
                
                # Create withdrawal transaction
                Transaction.objects.create(
                    user=user,
                    transaction_type='withdrawal',
                    amount=amount_decimal,
                    balance_before=current_balance,
                    balance_after=current_balance - amount_decimal,
                    description=f"Withdrawal to M-Pesa {phone}",
                    metadata={
                        'phone': phone,
                        'withdrawal_method': 'mpesa',
                        'status': 'pending_processing'
                    },
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                messages.success(request, f"Withdrawal request for KES {amount_decimal:,} submitted successfully!")
                
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
        else:
            messages.error(request, "All fields are required!")
    
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@login_required
def process_investment(request, venture_id):
    """Process an investment in a venture using wallet balance"""
    venture = get_object_or_404(Venture, id=venture_id)
    
    # Check if venture is open for investment
    if not venture.is_open_for_investment:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'This venture is not currently accepting investments.'
            }, status=400)
        messages.error(request, 'This venture is not currently accepting investments.')
        return redirect('venture_detail', venture_id=venture.id)
    
    if request.method == 'POST':
        try:
            # Get number of shares from form
            shares = int(request.POST.get('shares', 0))
            
            # Validate shares
            if shares < 1:
                raise ValueError('You must purchase at least 1 share.')
            
            if shares > venture.available_shares:
                raise ValueError(f'Only {venture.available_shares} shares are available.')
            
            # Calculate investment amount
            amount_invested = Decimal(shares) * venture.price_per_share
            
            # Get or create user wallet
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            
            # Check if user has sufficient balance
            if wallet.available_balance < amount_invested:
                raise ValueError(
                    f'Insufficient balance. Available: Ksh {wallet.available_balance:,.0f}, '
                    f'Required: Ksh {amount_invested:,.0f}'
                )
            
            # Use database transaction to ensure all operations succeed or fail together
            with db_transaction.atomic():
                # Deduct amount from wallet
                balance_before = wallet.balance
                wallet.balance -= amount_invested
                wallet.save()
                
                # Create investment
                investment = Investment.objects.create(
                    investor=request.user,
                    venture=venture,
                    shares=shares,
                    amount_invested=amount_invested,
                    share_price_at_purchase=venture.price_per_share,
                    status='confirmed',  # Immediately confirmed since using wallet balance
                    confirmed_at=timezone.now()
                )
                
                # Update venture shares issued
                venture.shares_issued += shares
                venture.save()
                
                # Create transaction record
                transaction = Transaction.objects.create(
                    user=request.user,
                    transaction_type='investment',
                    payment_method='wallet',
                    reference=generate_transaction_reference(),
                    amount=amount_invested,
                    fee=0,
                    net_amount=amount_invested,
                    balance_before=balance_before,
                    balance_after=wallet.balance,
                    investment=investment,
                    description=f"Investment in {venture.name}: {shares} shares @ Ksh {venture.price_per_share:,.2f}",
                    status='completed',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    initiated_at=timezone.now(),
                    completed_at=timezone.now()
                )
                
                # Update user portfolio
                portfolio, created = UserPortfolio.objects.get_or_create(user=request.user)
                portfolio.update_portfolio()
                
                # Update finance summary
                from .models import FinanceSummary
                summary, created = FinanceSummary.objects.get_or_create(user=request.user)
                summary.total_invested += amount_invested
                summary.save()
                
                # Create notification
                notification = Notification.objects.create(
                    user=request.user,
                    notification_type='investment',
                    title='Investment Successful',
                    message=f'You have successfully invested Ksh {amount_invested:,.0f} in {venture.name}.',
                    investment=investment,
                    venture=venture
                )
                
                # Create audit log
                AuditLog.objects.create(
                    user=request.user,
                    action='investment',
                    model_name='Investment',
                    object_id=str(investment.id),
                    details={
                        'venture_id': venture.id,
                        'venture_name': venture.name,
                        'venture_code': venture.code,
                        'shares': shares,
                        'amount': str(amount_invested),
                        'price_per_share': str(venture.price_per_share),
                        'balance_after': str(wallet.balance)
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            
            # Return JSON response for AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'investment_id': investment.id,
                    'shares': shares,
                    'amount': float(amount_invested),
                    'balance_after': float(wallet.balance),
                    'reference': transaction.reference,
                    'redirect_url': reverse('investment_success', args=[investment.id])
                })
            
            messages.success(
                request, 
                f'🎉 Investment successful! You purchased {shares} shares in {venture.name} '
                f'for Ksh {amount_invested:,.0f}.'
            )
            return redirect('investment_detail', investment_id=investment.id)
            
        except ValueError as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=400)
            messages.error(request, str(e))
            return redirect('venture_detail', venture_id=venture.id)
            
        except Wallet.DoesNotExist:
            error_msg = 'Please add funds to your wallet before investing.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg,
                    'redirect_url': reverse('finance:deposit')
                }, status=400)
            messages.error(request, error_msg)
            return redirect('finance:deposit')
            
        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Investment error for user {request.user.id}: {str(e)}", exc_info=True)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'An error occurred while processing your investment. Please try again.'
                }, status=500)
            messages.error(request, 'An error occurred while processing your investment.')
            return redirect('venture_detail', venture_id=venture.id)
    
    return redirect('venture_detail', venture_id=venture.id)


@login_required
def investment_success(request, investment_id):
    """Investment success page"""
    investment = get_object_or_404(
        Investment, 
        id=investment_id, 
        investor=request.user
    )
    
    context = {
        'investment': investment,
        'transaction': investment.transactions.first()
    }
    
    return render(request, 'core/investment_success.html', context)


@login_required
def investment_detail(request, investment_id):
    """View investment details"""
    investment = get_object_or_404(
        Investment,
        id=investment_id,
        investor=request.user
    )
    
    # Get related transactions
    transactions = investment.transactions.all()
    
    # Get dividends
    dividends = investment.dividends.all()
    
    context = {
        'investment': investment,
        'transactions': transactions,
        'dividends': dividends,
        'current_value': investment.current_value,
        'profit_loss': investment.profit_loss,
        'return_percentage': (investment.profit_loss / investment.amount_invested * 100) if investment.amount_invested > 0 else 0
    }
    
    return render(request, 'core/investment_detail.html', context)


@login_required
def bulk_investment(request, venture_id):
    """Handle bulk/multiple share purchases"""
    venture = get_object_or_404(Venture, id=venture_id)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            shares = int(data.get('shares', 0))
            
            # Process the investment using the main function
            # This is a helper for the AJAX bulk purchase feature
            return process_investment(request, venture_id)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def terms_of_service(request):
    """Terms of service page"""
    return render(request, 'core/terms_of_service.html')

def investment_agreement(request):
    """Investment agreement page"""
    return render(request, 'core/investment_agreement.html')