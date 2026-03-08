from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib import messages
from django.views.decorators.http import require_GET, require_POST
import json
from datetime import datetime, timedelta
import string
import re
import random
from decimal import Decimal, InvalidOperation
from django.conf import settings
import requests
import logging
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction as db_transaction
from django.core.cache import cache

from .models import Transaction, Wallet, FinanceSummary
from core.models import Notification, AuditLog

# Configure logger
logger = logging.getLogger(__name__)

from intasend import APIService

# Initialize IntaSend service
intasend_service = APIService(
    token=settings.INTASEND_TOKEN,
    publishable_key=settings.INTASEND_PUBLISHABLE_KEY
)

from .models import (
    Wallet, Transaction, Loan, LoanRepayment, 
    PaymentMethod, FinanceSummary, User
)


# ============================================
# MAIN FINANCE DASHBOARD
# ============================================

def id_generator(size=12, chars=string.ascii_uppercase + string.digits):
    """Generate random reference ID"""
    return ''.join(random.choice(chars) for _ in range(size))

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def clean_phone_number(phone):
    """Clean and validate phone number"""
    if not phone:
        return None
    
    # Remove all non-digits
    phone = re.sub(r'\D', '', phone)
    
    # Convert 9-digit number (712345678) to 10-digit (0712345678)
    if len(phone) == 9:
        phone = f"0{phone}"
    
    # Validate format
    if len(phone) == 10 and phone.startswith('07'):
        return phone
    
    return None

@login_required
@require_GET
def finance_dashboard(request):
    """Main finance dashboard with wallet overview and recent activity"""
    user = request.user
    
    # Get or create wallet
    wallet, created = Wallet.objects.get_or_create(user=user)
    
    # Get or create finance summary
    summary, created = FinanceSummary.objects.get_or_create(user=user)
    summary.calculate_summary()
    
    # Get recent transactions
    recent_transactions = Transaction.objects.filter(
        user=user
    ).select_related('investment', 'loan').order_by('-initiated_at')[:10]
    
    # Get active loans
    active_loans = Loan.objects.filter(
        user=user,
        status__in=['approved', 'active']
    ).order_by('-approved_at')[:5]
    
    # Get saved payment methods
    payment_methods = PaymentMethod.objects.filter(
        user=user,
        is_active=True
    )[:4]
    
    # Calculate daily limits
    today = timezone.now().date()
    today_deposits = Transaction.objects.filter(
        user=user,
        transaction_type='deposit',
        status='completed',
        initiated_at__date=today
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    today_withdrawals = Transaction.objects.filter(
        user=user,
        transaction_type='withdrawal',
        status='completed',
        initiated_at__date=today
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    wallet.remaining_daily_deposit = max(
        wallet.daily_deposit_limit - today_deposits, 
        Decimal('0')
    )
    wallet.remaining_daily_withdrawal = max(
        wallet.daily_withdrawal_limit - today_withdrawals,
        Decimal('0')
    )
    wallet.save()
    
    context = {
        'wallet': wallet,
        'summary': summary,
        'recent_transactions': recent_transactions,
        'active_loans': active_loans,
        'payment_methods': payment_methods,
        'today_deposits': today_deposits,
        'today_withdrawals': today_withdrawals,
    }
    
    return render(request, 'finance/finance_dashboard.html', context)


# ============================================
# TRANSACTION HISTORY
# ============================================

@login_required
@require_GET
def transaction_history(request):
    """View all transactions with filtering and pagination"""
    user = request.user
    
    # Base queryset
    transactions = Transaction.objects.filter(user=user).select_related('investment', 'loan')
    
    # Apply filters
    transaction_type = request.GET.get('type')
    if transaction_type and transaction_type != 'all':
        transactions = transactions.filter(transaction_type=transaction_type)
    
    status = request.GET.get('status')
    if status and status != 'all':
        transactions = transactions.filter(status=status)
    
    date_from = request.GET.get('date_from')
    if date_from:
        transactions = transactions.filter(initiated_at__date__gte=date_from)
    
    date_to = request.GET.get('date_to')
    if date_to:
        transactions = transactions.filter(initiated_at__date__lte=date_to)
    
    search = request.GET.get('search')
    if search:
        transactions = transactions.filter(
            Q(reference__icontains=search) |
            Q(description__icontains=search) |
            Q(mpesa_code__icontains=search)
        )
    
    # Ordering
    order_by = request.GET.get('order_by', '-initiated_at')
    transactions = transactions.order_by(order_by)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(transactions, 20)
    transactions_page = paginator.get_page(page)
    
    # Get filter options for dropdowns
    transaction_types = Transaction.TRANSACTION_TYPES
    status_choices = Transaction.STATUS_CHOICES
    
    context = {
        'transactions': transactions_page,
        'paginator': paginator,
        'transaction_types': transaction_types,
        'status_choices': status_choices,
        'current_filters': {
            'type': transaction_type,
            'status': status,
            'date_from': date_from,
            'date_to': date_to,
            'search': search,
            'order_by': order_by,
        }
    }
    
    return render(request, 'finance/transaction_history.html', context)


@login_required
@require_GET
def transaction_detail(request, transaction_id):
    """View single transaction details"""
    transaction = get_object_or_404(
        Transaction,
        id=transaction_id,
        user=request.user
    )
    
    context = {
        'transaction': transaction
    }
    
    return render(request, 'finance/transaction_detail.html', context)


# ============================================
# DEPOSITS (M-PESA)
# ============================================

@login_required
@require_GET
def deposit(request):
    """Deposit funds page"""
    user = request.user
    wallet, created = Wallet.objects.get_or_create(user=user)
    
    # Get saved M-Pesa numbers
    saved_methods = PaymentMethod.objects.filter(
        user=user,
        method_type='mpesa',
        is_active=True
    )
    
    context = {
        'wallet': wallet,
        'saved_methods': saved_methods,
        'min_deposit': 100,
        'max_deposit': 150000,
    }
    
    return render(request, 'finance/deposit.html', context)


@login_required
@require_POST
def initiate_deposit(request):
    """
    Initiate M-Pesa STK Push via IntaSend
    Supports both AJAX (JSON) and form submissions
    """
    user = request.user
    
    try:
        # ============================================
        # 1. PARSE REQUEST DATA
        # ============================================
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = request.POST.dict()
        else:
            data = request.POST.dict()
        
        # Extract phone and amount - support both 'tel' and 'phone' field names
        phone_raw = data.get('tel', data.get('phone', '')).strip()
        amount_str = data.get('amount', '0')
        
        # ============================================
        # 2. VALIDATE PHONE NUMBER
        # ============================================
        phone = clean_phone_number(phone_raw)
        
        if not phone:
            error_msg = 'Please enter a valid M-Pesa number (254XXXXXXXX)'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=400)
            else:
                messages.error(request, error_msg)
                return redirect('finance:deposit')
        
        # Format phone for IntaSend (ensure it's integer without leading zero)
        if phone.startswith('0'):
            intasend_phone = int(f"254{phone[1:]}")
        elif phone.startswith('254'):
            intasend_phone = int(phone)
        else:
            intasend_phone = int(f"254{phone}")
        
        # ============================================
        # 3. VALIDATE AMOUNT
        # ============================================
        try:
            amount = Decimal(str(amount_str))
        except (InvalidOperation, TypeError, ValueError):
            error_msg = 'Invalid amount format'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=400)
            else:
                messages.error(request, error_msg)
                return redirect('finance:deposit')
        
        # Amount range validation
        MIN_DEPOSIT = getattr(settings, 'MIN_DEPOSIT', 100)
        MAX_DEPOSIT = getattr(settings, 'MAX_DEPOSIT', 150000)
        
        if amount < MIN_DEPOSIT:
            error_msg = f'Minimum deposit amount is KES {MIN_DEPOSIT:,.0f}'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=400)
            else:
                messages.error(request, error_msg)
                return redirect('finance:deposit')
        
        if amount > MAX_DEPOSIT:
            error_msg = f'Maximum deposit amount is KES {MAX_DEPOSIT:,.0f}'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=400)
            else:
                messages.error(request, error_msg)
                return redirect('finance:deposit')
        
        # ============================================
        # 4. GET OR CREATE WALLET
        # ============================================
        wallet, created = Wallet.objects.get_or_create(user=user)
        
        # ============================================
        # 5. CHECK DAILY LIMIT
        # ============================================
        if amount > wallet.remaining_daily_deposit:
            error_msg = f'Daily deposit limit of KES {wallet.daily_deposit_limit:,.0f} exceeded. Remaining: KES {wallet.remaining_daily_deposit:,.0f}'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=400)
            else:
                messages.error(request, error_msg)
                return redirect('finance:deposit')
        
        # ============================================
        # 6. GENERATE REFERENCE
        # ============================================
        reference = f"DEP-{timezone.now().strftime('%Y%m%d%H%M%S')}-{user.id}-{id_generator(6)}"
        
        # ============================================
        # 7. CREATE PENDING TRANSACTION
        # ============================================
        transaction = Transaction.objects.create(
            user=user,
            transaction_type='deposit',
            payment_method='mpesa',
            reference=reference,
            amount=amount,
            fee=0,
            net_amount=amount,
            balance_before=wallet.balance,
            balance_after=wallet.balance,  # Will be updated on callback
            phone_number=phone,
            description=f"M-Pesa deposit of KES {amount:,.0f} from {phone}",
            status='pending',
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
        
        # ============================================
        # 8. CALL INTASEND API
        # ============================================
        try:
            # Ensure user has an email
            user_email = user.email
            if not user_email:
                # If user doesn't have email, use a fallback or generate one
                # This shouldn't happen in your system, but just in case
                user_email = f"user_{user.id}@airvyb.co.ke"
            
            # Log the request for debugging
            logger.info(f"Initiating IntaSend STK Push for user {user.id}: Phone={intasend_phone}, Amount={amount}, Email={user_email}")
            
            # Initiate STK Push with IntaSend
            response = intasend_service.collect.mpesa_stk_push(
                phone_number=intasend_phone,
                email=user_email,  # Email is required - use user's email
                amount=int(amount),  # Amount must be integer
                narrative=f"Wallet Deposit - {user.get_full_name() or user.username}"
            )
            
            # Log the response for debugging
            logger.info(f"IntaSend API Response: {response}")
            
            # ============================================
            # 9. HANDLE API RESPONSE
            # ============================================
            # Check if response has the expected structure
            if response and isinstance(response, dict):
                # Check for error in response
                if 'error' in response:
                    error_message = response.get('error', 'Unknown error')
                    error_detail = response.get('detail', '')
                    
                    if error_detail:
                        error_message = f"{error_message}: {error_detail}"
                    
                    transaction.status = 'failed'
                    transaction.failed_at = timezone.now()
                    transaction.metadata['api_error'] = response
                    transaction.save()
                    
                    logger.error(f"IntaSend STK Push failed: {error_message}")
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': error_message
                        }, status=400)
                    else:
                        messages.error(request, error_message)
                        return redirect('finance:deposit')
                
                # Check for success response with id and invoice_id
                if response.get('id') and response.get('invoice'):
                    # Extract IntaSend specific IDs
                    payment_id = response.get('id')
                    invoice_data = response.get('invoice', {})
                    invoice_id = invoice_data.get('invoice_id')
                    
                    if not invoice_id:
                        # Try alternative path
                        invoice_id = response.get('invoice_id')
                    
                    # Update transaction - successfully initiated
                    transaction.status = 'processing'
                    transaction.processed_at = timezone.now()
                    transaction.metadata.update({
                        'intasend_payment_id': payment_id,
                        'intasend_invoice_id': invoice_id,
                        'api_response': response
                    })
                    transaction.save()
                    
                    logger.info(f"STK Push initiated successfully for transaction {transaction.id}: Invoice ID {invoice_id}")
                    
                    # Return success response
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'STK push initiated successfully! Check your phone to complete payment.',
                            'transaction': {
                                'id': transaction.id,
                                'reference': transaction.reference,
                                'amount': float(transaction.amount),
                                'phone': transaction.phone_number,
                                'status': transaction.status,
                                'initiated_at': transaction.initiated_at,
                                'invoice_id': invoice_id  # Return for frontend polling
                            }
                        })
                    else:
                        messages.success(request, 
                            f"STK push initiated successfully! Check your phone to complete payment of KES {amount:,.0f}."
                        )
                        return redirect('finance:deposit')
                else:
                    # Unexpected response structure
                    error_message = 'Unexpected response from payment service'
                    
                    transaction.status = 'failed'
                    transaction.failed_at = timezone.now()
                    transaction.metadata['api_error'] = response
                    transaction.save()
                    
                    logger.error(f"IntaSend unexpected response: {response}")
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': error_message
                        }, status=400)
                    else:
                        messages.error(request, error_message)
                        return redirect('finance:deposit')
            else:
                # Empty or invalid response
                error_message = 'Invalid response from payment service'
                
                transaction.status = 'failed'
                transaction.failed_at = timezone.now()
                transaction.metadata['api_error'] = response
                transaction.save()
                
                logger.error(f"IntaSend invalid response: {response}")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    }, status=400)
                else:
                    messages.error(request, error_message)
                    return redirect('finance:deposit')
        
        except Exception as e:
            # IntaSend API exception
            error_msg = 'Payment service temporarily unavailable. Please try again later.'
            
            transaction.status = 'failed'
            transaction.failed_at = timezone.now()
            transaction.metadata['error'] = str(e)
            transaction.save()
            
            logger.error(f"IntaSend API error for user {user.id}: {str(e)}", exc_info=True)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=502)
            else:
                messages.error(request, error_msg)
                return redirect('finance:deposit')
    
    except Wallet.DoesNotExist:
        error_msg = 'Wallet not found. Please contact support.'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=404)
        else:
            messages.error(request, error_msg)
            return redirect('finance:dashboard')
    
    except Exception as e:
        # Global exception handler
        logger.error(f"Deposit initiation error for user {user.id}: {str(e)}", exc_info=True)
        
        error_msg = 'An error occurred while processing your request. Please try again.'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=500)
        else:
            messages.error(request, error_msg)
            return redirect('finance:dashboard')

@login_required
@require_GET
def check_deposit_status(request, transaction_id):
    """Check deposit transaction status - supports both local and IntaSend status"""
    transaction = get_object_or_404(
        Transaction,
        id=transaction_id,
        user=request.user,
        transaction_type='deposit'
    )
    
    # If transaction has IntaSend invoice_id and is still processing, check with IntaSend
    if transaction.status in ['pending', 'processing'] and transaction.metadata.get('intasend_invoice_id'):
        try:
            invoice_id = transaction.metadata['intasend_invoice_id']
            
            # Check status with IntaSend
            status_response = intasend_service.collect.status(invoice_id=invoice_id)
            
            if status_response and 'invoice' in status_response:
                invoice = status_response['invoice']
                state = invoice.get('state')
                failed_reason = invoice.get('failed_reason')
                
                # Map IntaSend states to your statuses
                status_mapping = {
                    'PENDING': 'pending',
                    'PROCESSING': 'processing',
                    'COMPLETE': 'completed',
                    'FAILED': 'failed'
                }
                
                new_status = status_mapping.get(state, transaction.status)
                
                # Update transaction if status changed
                if new_status != transaction.status:
                    with db_transaction.atomic():
                        transaction.status = new_status
                        
                        if state == 'COMPLETE':
                            transaction.completed_at = timezone.now()
                            transaction.mpesa_code = invoice.get('mpesa_receipt_number')
                            
                            # Update wallet balance
                            wallet = Wallet.objects.get(user=request.user)
                            wallet.balance += transaction.amount
                            wallet.save()
                            
                            transaction.balance_after = wallet.balance
                            
                        elif state == 'FAILED':
                            transaction.failed_at = timezone.now()
                            transaction.metadata['failed_reason'] = failed_reason
                        
                        transaction.metadata['last_status_check'] = {
                            'timestamp': timezone.now().isoformat(),
                            'state': state,
                            'failed_reason': failed_reason
                        }
                        transaction.save()
                
                return JsonResponse({
                    'success': True,
                    'status': transaction.status,
                    'intasend_state': state,
                    'mpesa_code': transaction.mpesa_code,
                    'failed_reason': failed_reason,
                    'completed_at': transaction.completed_at,
                    'balance_after': float(transaction.balance_after) if transaction.balance_after else None
                })
                
        except Exception as e:
            logger.error(f"IntaSend status check error: {str(e)}", exc_info=True)
            # Fall back to local status
    
    # Return local status if IntaSend check not needed or failed
    return JsonResponse({
        'success': True,
        'status': transaction.status,
        'mpesa_code': transaction.mpesa_code,
        'completed_at': transaction.completed_at,
        'balance_after': float(transaction.balance_after) if transaction.balance_after else None
    })


@csrf_exempt
@require_POST
def deposit_callback(request):
    """
    Handle IntaSend payment callback for deposits
    """
    try:
        # Parse callback data
        payload = json.loads(request.body)
        
        # Extract IntaSend specific fields
        invoice_id = payload.get('invoice_id')
        state = payload.get('state')
        failed_reason = payload.get('failed_reason')
        mpesa_receipt = payload.get('mpesa_receipt_number')
        
        if not invoice_id:
            logger.error("Missing invoice_id in callback")
            return JsonResponse({'error': 'Missing invoice_id'}, status=400)
        
        # Find transaction by invoice_id in metadata
        try:
            transaction = Transaction.objects.get(
                metadata__intasend_invoice_id=invoice_id,
                transaction_type='deposit'
            )
        except Transaction.DoesNotExist:
            # Try to find by searching in metadata JSON
            transactions = Transaction.objects.filter(
                transaction_type='deposit',
                metadata__has_key='intasend_invoice_id'
            )
            transaction = None
            for t in transactions:
                if t.metadata.get('intasend_invoice_id') == invoice_id:
                    transaction = t
                    break
            
            if not transaction:
                logger.error(f"Transaction not found for invoice_id: {invoice_id}")
                return JsonResponse({'error': 'Transaction not found'}, status=404)
        
        # Process based on state
        with db_transaction.atomic():
            # Get user's wallet
            wallet = Wallet.objects.get(user=transaction.user)
            
            # Map IntaSend states to your statuses
            if state == 'COMPLETE':
                # Update transaction
                transaction.status = 'completed'
                transaction.completed_at = timezone.now()
                transaction.mpesa_code = mpesa_receipt
                
                # Update wallet balance
                wallet.balance += transaction.amount
                wallet.save()
                
                transaction.balance_after = wallet.balance
                transaction.metadata['callback_data'] = payload
                transaction.save()
                
                logger.info(f"Deposit completed for user {transaction.user.id}: KES {transaction.amount}")
                
                # Send success notification (optional)
                # send_deposit_success_notification(transaction)
                
                return JsonResponse({'success': True, 'status': 'completed'})
            
            elif state == 'FAILED':
                transaction.status = 'failed'
                transaction.failed_at = timezone.now()
                transaction.metadata['failed_reason'] = failed_reason
                transaction.metadata['callback_data'] = payload
                transaction.save()
                
                logger.info(f"Deposit failed for user {transaction.user.id}: {failed_reason}")
                
                # Send failure notification (optional)
                # send_deposit_failed_notification(transaction, failed_reason)
                
                return JsonResponse({'success': True, 'status': 'failed'})
            
            elif state == 'PENDING':
                transaction.status = 'pending'
                transaction.metadata['callback_data'] = payload
                transaction.save()
                
                return JsonResponse({'success': True, 'status': 'pending'})
            
            else:
                # Other states (PROCESSING, etc.)
                transaction.metadata['callback_data'] = payload
                transaction.save()
                return JsonResponse({'success': True, 'status': state.lower()})
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in callback")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    except Wallet.DoesNotExist:
        logger.error(f"Wallet not found for transaction {invoice_id}")
        return JsonResponse({'error': 'Wallet not found'}, status=404)
    
    except Exception as e:
        logger.error(f"Deposit callback error: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)
# ============================================
# WITHDRAWALS
# ============================================

@login_required
@require_GET
def withdrawal(request):
    """Withdrawal page"""
    user = request.user
    wallet, created = Wallet.objects.get_or_create(user=user)
    
    # Get saved M-Pesa numbers
    saved_methods = PaymentMethod.objects.filter(
        user=user,
        method_type='mpesa',
        is_active=True
    )
    
    context = {
        'wallet': wallet,
        'saved_methods': saved_methods,
        'min_withdrawal': 500,
        'max_withdrawal': 50000,
    }
    
    return render(request, 'finance/withdrawal.html', context)


@login_required
@require_POST
def process_withdrawal(request):
    """Process withdrawal request"""
    try:
        data = json.loads(request.body) if request.body else request.POST
        
        phone = data.get('phone', '').strip()
        amount = Decimal(data.get('amount', 0))
        
        wallet = get_object_or_404(Wallet, user=request.user)
        
        # Validation
        if not phone or len(phone) != 10 or not phone.startswith('07'):
            return JsonResponse({
                'success': False,
                'error': 'Please enter a valid M-Pesa number (07XXXXXXXX)'
            }, status=400)
        
        if amount < 500 or amount > 50000:
            return JsonResponse({
                'success': False,
                'error': 'Amount must be between KES 500 and KES 50,000'
            }, status=400)
        
        if amount > wallet.available_balance:
            return JsonResponse({
                'success': False,
                'error': f'Insufficient balance. Available: KES {wallet.available_balance}'
            }, status=400)
        
        if amount > wallet.remaining_daily_withdrawal:
            return JsonResponse({
                'success': False,
                'error': f'Daily withdrawal limit of KES {wallet.daily_withdrawal_limit} exceeded. Remaining: KES {wallet.remaining_daily_withdrawal}'
            }, status=400)
        
        # Generate reference
        reference = f"WDR-{timezone.now().strftime('%Y%m%d%H%M%S')}-{request.user.id}"
        
        # Create pending transaction
        transaction = Transaction.objects.create(
            user=request.user,
            transaction_type='withdrawal',
            payment_method='mpesa',
            reference=reference,
            amount=amount,
            net_amount=amount,
            fee=0,
            balance_before=wallet.balance,
            balance_after=wallet.balance - amount,
            phone_number=phone,
            description=f"M-Pesa withdrawal of KES {amount} to {phone}",
            status='pending'
        )
        
        # Update wallet
        wallet.balance -= amount
        wallet.total_withdrawn += amount
        wallet.last_withdrawal_at = timezone.now()
        wallet.save()
        
        transaction.balance_after = wallet.balance
        transaction.status = 'completed'
        transaction.completed_at = timezone.now()
        transaction.save()
        
        # Update finance summary
        summary, created = FinanceSummary.objects.get_or_create(user=request.user)
        summary.calculate_summary()
        
        return JsonResponse({
            'success': True,
            'message': 'Withdrawal processed successfully',
            'transaction': {
                'id': transaction.id,
                'reference': transaction.reference,
                'amount': float(transaction.amount),
                'phone': transaction.phone_number,
                'balance_after': float(transaction.balance_after)
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================
# LOANS / BORROWING
# ============================================

@login_required
@require_GET
def loans(request):
    """Loan management dashboard"""
    user = request.user
    
    # Get all loans
    all_loans = Loan.objects.filter(user=user).order_by('-applied_at')
    
    # Get active loans
    active_loans = all_loans.filter(status__in=['approved', 'active'])
    
    # Calculate eligibility
    wallet, created = Wallet.objects.get_or_create(user=user)
    summary, created = FinanceSummary.objects.get_or_create(user=user)
    
    # Simple eligibility calculation
    # Max loan = 50% of total deposits + investments
    max_eligible = (summary.total_deposits * Decimal('0.5')) + (summary.total_invested * Decimal('0.3'))
    max_eligible = min(max_eligible, 500000)  # Cap at 500k
    
    is_eligible = max_eligible >= 10000 and wallet.available_balance >= 1000
    
    context = {
        'all_loans': all_loans,
        'active_loans': active_loans,
        'wallet': wallet,
        'summary': summary,
        'max_eligible': max_eligible,
        'is_eligible': is_eligible,
        'loan_purposes': Loan.LOAN_PURPOSES,
        'repayment_frequencies': Loan.REPAYMENT_FREQUENCY,
    }
    
    return render(request, 'finance/loans.html', context)


@login_required
@require_POST
def apply_loan(request):
    """Apply for a new loan"""
    try:
        data = json.loads(request.body) if request.body else request.POST
        
        amount = Decimal(data.get('amount', 0))
        purpose = data.get('purpose')
        tenure_months = int(data.get('tenure_months', 12))
        repayment_frequency = data.get('repayment_frequency', 'monthly')
        
        # Validation
        if amount < 10000:
            return JsonResponse({
                'success': False,
                'error': 'Minimum loan amount is KES 10,000'
            }, status=400)
        
        if amount > 500000:
            return JsonResponse({
                'success': False,
                'error': 'Maximum loan amount is KES 500,000'
            }, status=400)
        
        if tenure_months < 1 or tenure_months > 60:
            return JsonResponse({
                'success': False,
                'error': 'Loan tenure must be between 1 and 60 months'
            }, status=400)
        
        # Check eligibility
        summary, created = FinanceSummary.objects.get_or_create(user=request.user)
        max_eligible = (summary.total_deposits * Decimal('0.5')) + (summary.total_invested * Decimal('0.3'))
        max_eligible = min(max_eligible, 500000)
        
        if amount > max_eligible:
            return JsonResponse({
                'success': False,
                'error': f'You are eligible for a maximum loan of KES {max_eligible:,.0f}'
            }, status=400)
        
        # Calculate interest rate (based on amount and tenure)
        if amount <= 50000:
            interest_rate = 12.0
        elif amount <= 200000:
            interest_rate = 10.0
        else:
            interest_rate = 8.0
        
        # Create loan application
        reference = f"LOAN-{timezone.now().strftime('%Y%m%d%H%M%S')}-{request.user.id}"
        
        loan = Loan.objects.create(
            user=request.user,
            reference=reference,
            purpose=purpose,
            amount_requested=amount,
            amount_approved=amount,  # Auto-approve for demo
            interest_rate=interest_rate,
            tenure_months=tenure_months,
            repayment_frequency=repayment_frequency,
            status='approved',  # Auto-approve for demo
            approved_by=request.user,
            approved_at=timezone.now()
        )
        
        # Calculate repayments
        loan.calculate_repayment()
        loan.save()
        
        # Disburse loan to wallet
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        
        # Create disbursement transaction
        transaction = Transaction.objects.create(
            user=request.user,
            transaction_type='loan',
            payment_method='wallet',
            reference=f"DISB-{reference}",
            amount=amount,
            net_amount=amount,
            balance_before=wallet.balance,
            balance_after=wallet.balance + amount,
            loan=loan,
            description=f"Loan disbursement: {reference}",
            status='completed',
            completed_at=timezone.now()
        )
        
        # Update wallet
        wallet.balance += amount
        wallet.save()
        
        loan.disbursed_at = timezone.now()
        loan.save()
        
        # Update finance summary
        summary.calculate_summary()
        
        return JsonResponse({
            'success': True,
            'message': 'Loan application approved and disbursed!',
            'loan': {
                'id': loan.id,
                'reference': loan.reference,
                'amount': float(loan.amount_approved),
                'interest_rate': float(loan.interest_rate),
                'total_repayable': float(loan.total_repayable),
                'monthly_installment': float(loan.monthly_installment)
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_GET
def loan_detail(request, loan_id):
    """View single loan details"""
    loan = get_object_or_404(Loan, id=loan_id, user=request.user)
    
    # Get repayment schedule
    repayments = loan.repayments.all().order_by('due_date')
    
    # Generate future repayment schedule if not yet created
    if loan.status in ['approved', 'active'] and not repayments.exists():
        # In production, you'd generate the full schedule here
        pass
    
    context = {
        'loan': loan,
        'repayments': repayments,
        'progress': loan.progress_percentage
    }
    
    return render(request, 'finance/loan_detail.html', context)


@login_required
@require_POST
def repay_loan(request, loan_id):
    """Make a loan repayment"""
    try:
        loan = get_object_or_404(Loan, id=loan_id, user=request.user)
        
        data = json.loads(request.body) if request.body else request.POST
        amount = Decimal(data.get('amount', 0))
        
        wallet = get_object_or_404(Wallet, user=request.user)
        
        # Validation
        if amount <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Please enter a valid amount'
            }, status=400)
        
        if amount > wallet.available_balance:
            return JsonResponse({
                'success': False,
                'error': f'Insufficient balance. Available: KES {wallet.available_balance:,.0f}'
            }, status=400)
        
        if amount > loan.outstanding_balance:
            amount = loan.outstanding_balance
        
        # Calculate principal and interest portions
        # Simplified: 70% principal, 30% interest for this payment
        principal_paid = amount * Decimal('0.7')
        interest_paid = amount * Decimal('0.3')
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=request.user,
            transaction_type='loan_repayment',
            payment_method='wallet',
            reference=f"REPAY-{timezone.now().strftime('%Y%m%d%H%M%S')}-{loan_id}",
            amount=amount,
            net_amount=amount,
            balance_before=wallet.balance,
            balance_after=wallet.balance - amount,
            loan=loan,
            description=f"Loan repayment for {loan.reference}",
            status='completed',
            completed_at=timezone.now()
        )
        
        # Create repayment record
        repayment = LoanRepayment.objects.create(
            loan=loan,
            transaction=transaction,
            amount=amount,
            principal_paid=principal_paid,
            interest_paid=interest_paid,
            due_date=timezone.now().date(),
            paid_at=timezone.now()
        )
        
        # Update loan
        loan.amount_paid += amount
        loan.outstanding_balance = loan.total_repayable - loan.amount_paid
        
        if loan.outstanding_balance <= 0:
            loan.status = 'repaid'
            loan.completed_at = timezone.now()
        
        loan.save()
        
        # Update wallet
        wallet.balance -= amount
        wallet.save()
        
        # Update finance summary
        summary, created = FinanceSummary.objects.get_or_create(user=request.user)
        summary.calculate_summary()
        
        return JsonResponse({
            'success': True,
            'message': 'Repayment successful!',
            'transaction': {
                'id': transaction.id,
                'reference': transaction.reference,
                'amount': float(transaction.amount),
                'balance_after': float(wallet.balance),
                'loan_balance': float(loan.outstanding_balance),
                'progress': loan.progress_percentage
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================
# PAYMENT METHODS
# ============================================

@login_required
@require_GET
def payment_methods(request):
    """Manage saved payment methods"""
    user = request.user
    
    methods = PaymentMethod.objects.filter(user=user, is_active=True)
    
    context = {
        'methods': methods
    }
    
    return render(request, 'finance/payment_methods.html', context)


@login_required
@require_POST
def add_payment_method(request):
    """Add a new payment method"""
    try:
        data = json.loads(request.body) if request.body else request.POST
        
        method_type = data.get('method_type')
        
        # Validate based on method type
        if method_type == 'mpesa':
            phone = data.get('phone', '').strip()
            
            if not phone or len(phone) != 10 or not phone.startswith('07'):
                return JsonResponse({
                    'success': False,
                    'error': 'Please enter a valid M-Pesa number'
                }, status=400)
            
            # Check if already exists
            existing = PaymentMethod.objects.filter(
                user=request.user,
                method_type='mpesa',
                phone_number=phone,
                is_active=True
            ).exists()
            
            if existing:
                return JsonResponse({
                    'success': False,
                    'error': 'This M-Pesa number is already saved'
                }, status=400)
            
            # Create new method
            method = PaymentMethod.objects.create(
                user=request.user,
                method_type='mpesa',
                phone_number=phone,
                is_default=not PaymentMethod.objects.filter(user=request.user).exists()
            )
            
            return JsonResponse({
                'success': True,
                'message': 'M-Pesa number saved successfully',
                'method': {
                    'id': method.id,
                    'phone': method.phone_number,
                    'is_default': method.is_default
                }
            })
            
        else:
            return JsonResponse({
                'success': False,
                'error': 'Unsupported payment method'
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def set_default_payment_method(request, method_id):
    """Set a payment method as default"""
    try:
        method = get_object_or_404(
            PaymentMethod,
            id=method_id,
            user=request.user
        )
        
        # Clear other defaults
        PaymentMethod.objects.filter(
            user=request.user,
            is_default=True
        ).update(is_default=False)
        
        # Set this as default
        method.is_default = True
        method.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Default payment method updated'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def delete_payment_method(request, method_id):
    """Delete a payment method"""
    try:
        method = get_object_or_404(
            PaymentMethod,
            id=method_id,
            user=request.user
        )
        
        was_default = method.is_default
        
        # Soft delete
        method.is_active = False
        method.save()
        
        # Set new default if needed
        if was_default:
            next_method = PaymentMethod.objects.filter(
                user=request.user,
                is_active=True
            ).first()
            
            if next_method:
                next_method.is_default = True
                next_method.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Payment method deleted'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================
# API ENDPOINTS FOR AJAX
# ============================================

@login_required
@require_GET
def get_wallet_balance(request):
    """Get current wallet balance"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    return JsonResponse({
        'success': True,
        'balance': float(wallet.balance),
        'available_balance': float(wallet.available_balance),
        'locked_balance': float(wallet.locked_balance),
        'remaining_daily_deposit': float(wallet.remaining_daily_deposit),
        'remaining_daily_withdrawal': float(wallet.remaining_daily_withdrawal)
    })


@login_required
@require_GET
def get_loan_eligibility(request):
    """Calculate loan eligibility"""
    summary, created = FinanceSummary.objects.get_or_create(user=request.user)
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    # Calculate max eligible
    max_eligible = (summary.total_deposits * Decimal('0.5')) + (summary.total_invested * Decimal('0.3'))
    max_eligible = min(max_eligible, 500000)
    
    # Check if user has existing active loans
    active_loans = Loan.objects.filter(
        user=request.user,
        status__in=['approved', 'active']
    ).aggregate(total=Sum('outstanding_balance'))['total'] or 0
    
    max_eligible = max(Decimal('0'), max_eligible - active_loans)
    
    return JsonResponse({
        'success': True,
        'max_eligible': float(max_eligible),
        'active_loans_total': float(active_loans),
        'is_eligible': max_eligible >= 10000,
        'credit_score': 750,  # Mock credit score
        'interest_rate_min': 8.0,
        'interest_rate_max': 15.0,
        'tenure_min': 1,
        'tenure_max': 60
    })


@login_required
@require_GET
def calculate_loan(request):
    """Calculate loan repayments before applying"""
    amount = Decimal(request.GET.get('amount', 0))
    tenure = int(request.GET.get('tenure', 12))
    
    if amount < 10000:
        return JsonResponse({'error': 'Minimum loan amount is KES 10,000'}, status=400)
    
    if amount > 500000:
        return JsonResponse({'error': 'Maximum loan amount is KES 500,000'}, status=400)
    
    # Calculate interest rate
    if amount <= 50000:
        interest_rate = 12.0
    elif amount <= 200000:
        interest_rate = 10.0
    else:
        interest_rate = 8.0
    
    # Calculate repayments
    total_interest = amount * (interest_rate / 100) * (tenure / 12)
    total_repayable = amount + total_interest
    monthly_installment = total_repayable / tenure
    
    return JsonResponse({
        'success': True,
        'amount': float(amount),
        'tenure_months': tenure,
        'interest_rate': interest_rate,
        'total_interest': float(total_interest),
        'total_repayable': float(total_repayable),
        'monthly_installment': float(monthly_installment)
    })

@csrf_exempt
@require_POST
def deposit_callback(request):
    """
    Handle PayHero M-Pesa payment callback
    Optimized for production with comprehensive error handling,
    atomic transactions, logging, and idempotency
    """
    request_id = id_generator(8)
    ip_address = get_client_ip(request)
    
    logger.info(f"[Callback:{request_id}] Received deposit callback from {ip_address}")
    
    try:
        # ============================================
        # 1. PARSE AND VALIDATE REQUEST
        # ============================================
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"[Callback:{request_id}] Invalid JSON payload: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON payload'
            }, status=400)
        
        # Extract response data (handle both nested and flat structures)
        response_data = payload.get('response', payload)
        
        # Extract transaction reference - check multiple possible field names
        reference = (
            response_data.get('ExternalReference') or 
            response_data.get('external_reference') or
            response_data.get('reference')
        )
        
        if not reference:
            logger.error(f"[Callback:{request_id}] Missing transaction reference in callback")
            return JsonResponse({
                'success': False,
                'error': 'Missing transaction reference'
            }, status=400)
        
        # Extract status - check multiple possible field names
        status = (
            response_data.get('Status') or 
            response_data.get('status') or
            response_data.get('resultCode') or
            response_data.get('ResultCode')
        )
        
        # Extract M-Pesa receipt number
        mpesa_code = (
            response_data.get('MpesaReceiptNumber') or
            response_data.get('mpesa_code') or
            response_data.get('transaction_id')
        )
        
        # Extract amount (if provided in callback)
        amount_str = (
            response_data.get('Amount') or
            response_data.get('amount')
        )
        
        # Extract phone number (if provided)
        phone = (
            response_data.get('PhoneNumber') or
            response_data.get('phone_number') or
            response_data.get('phone')
        )
        
        logger.info(f"[Callback:{request_id}] Processing callback for reference: {reference}, status: {status}")
        
        # ============================================
        # 2. CHECK IDEMPOTENCY (Prevent duplicate processing)
        # ============================================
        cache_key = f"callback_processed_{reference}"
        if cache.get(cache_key):
            logger.info(f"[Callback:{request_id}] Callback already processed for reference: {reference}")
            return JsonResponse({
                'success': True,
                'message': 'Callback already processed'
            })
        
        # Set cache with 1 hour expiry
        cache.set(cache_key, True, 3600)
        
        # ============================================
        # 3. FIND TRANSACTION
        # ============================================
        try:
            # Try primary reference first
            payment = Transaction.objects.select_related('user', 'user__wallet').get(reference=reference)
        except Transaction.DoesNotExist:
            # Try to find by metadata.external_reference
            try:
                payment = Transaction.objects.filter(
                    metadata__external_reference=reference
                ).select_related('user', 'user__wallet').first()
                
                if not payment:
                    logger.error(f"[Callback:{request_id}] Transaction not found for reference: {reference}")
                    return JsonResponse({
                        'success': False,
                        'error': 'Transaction not found'
                    }, status=404)
            except Exception as e:
                logger.error(f"[Callback:{request_id}] Error finding transaction: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'Transaction lookup failed'
                }, status=500)
        
        # Check if transaction already processed
        if payment.status in ['completed', 'success', 'failed', 'cancelled']:
            logger.info(f"[Callback:{request_id}] Transaction {reference} already processed with status: {payment.status}")
            return JsonResponse({
                'success': True,
                'message': f'Transaction already processed as {payment.status}',
                'status': payment.status
            })
        
        # ============================================
        # 4. DETERMINE PAYMENT STATUS
        # ============================================
        # Normalize status string
        if isinstance(status, str):
            status_lower = status.lower()
        elif isinstance(status, int):
            status_lower = 'success' if status == 0 else 'failed'
        else:
            status_lower = str(status).lower() if status else ''
        
        # Check for success conditions
        is_success = (
            status_lower in ['success', 'completed', 'paid', '0'] or
            status == 0 or
            status_lower == 'success' or
            response_data.get('success') in [True, 'true', 'True']
        )
        
        # Check for failed/cancelled conditions
        is_failed = (
            status_lower in ['failed', 'error', 'timeout', 'expired'] or
            status_lower == 'failed'
        )
        
        is_cancelled = (
            status_lower in ['cancelled', 'canceled', 'reversed'] or
            status_lower == 'cancelled'
        )
        
        # ============================================
        # 5. PROCESS PAYMENT WITH ATOMIC TRANSACTION
        # ============================================
        try:
            with db_transaction.atomic():
                # Update common fields
                payment.mpesa_code = mpesa_code or payment.mpesa_code
                payment.metadata['callback_payload'] = payload
                payment.metadata['callback_received_at'] = timezone.now().isoformat()
                payment.metadata['callback_ip'] = ip_address
                payment.metadata['callback_request_id'] = request_id
                
                # Update phone if provided
                if phone:
                    payment.phone_number = phone
                
                # Update amount if provided and matches
                if amount_str:
                    try:
                        callback_amount = Decimal(str(amount_str))
                        if callback_amount != payment.amount:
                            logger.warning(
                                f"[Callback:{request_id}] Amount mismatch: "
                                f"transaction={payment.amount}, callback={callback_amount}"
                            )
                            payment.metadata['amount_mismatch'] = {
                                'transaction': str(payment.amount),
                                'callback': str(callback_amount)
                            }
                    except (InvalidOperation, TypeError, ValueError):
                        pass
                
                # Process based on status
                if is_success:
                    # Get user wallet
                    wallet = payment.user.wallet
                    
                    # Check if already credited (double payment prevention)
                    if payment.status == 'completed':
                        logger.info(f"[Callback:{request_id}] Payment already completed for {reference}")
                    else:
                        # Calculate new balance
                        balance_before = wallet.balance
                        balance_after = wallet.balance + payment.amount
                        
                        # Update wallet
                        wallet.balance = balance_after
                        wallet.total_deposited += payment.amount
                        wallet.last_deposit_at = timezone.now()
                        wallet.remaining_daily_deposit = max(
                            0, 
                            wallet.remaining_daily_deposit - payment.amount
                        )
                        wallet.save(update_fields=[
                            'balance', 'total_deposited', 'last_deposit_at', 
                            'remaining_daily_deposit', 'updated_at'
                        ])
                        
                        # Update transaction
                        payment.status = 'completed'
                        payment.completed_at = timezone.now()
                        payment.processed_at = timezone.now()
                        payment.balance_before = balance_before
                        payment.balance_after = balance_after
                        payment.save(update_fields=[
                            'status', 'completed_at', 'processed_at', 
                            'balance_before', 'balance_after', 'mpesa_code',
                            'metadata', 'updated_at'
                        ])
                        
                        # Update finance summary (async or background task recommended)
                        try:
                            summary, _ = FinanceSummary.objects.get_or_create(user=payment.user)
                            summary.total_deposits += payment.amount
                            summary.save(update_fields=['total_deposits', 'last_calculated'])
                        except Exception as e:
                            logger.error(f"[Callback:{request_id}] Failed to update finance summary: {str(e)}")
                        
                        # Create notification
                        try:
                            Notification.objects.create(
                                user=payment.user,
                                notification_type='deposit',
                                title='Deposit Successful',
                                message=f'Your deposit of KES {payment.amount:,.0f} has been credited to your wallet.',
                                metadata={
                                    'transaction_id': payment.id,
                                    'transaction_reference': payment.reference,
                                    'amount': str(payment.amount),
                                    'mpesa_code': mpesa_code or ''
                                }
                            )
                        except Exception as e:
                            logger.error(f"[Callback:{request_id}] Failed to create notification: {str(e)}")
                        
                        # Create audit log
                        try:
                            AuditLog.objects.create(
                                user=payment.user,
                                action='payment_success',
                                model_name='Transaction',
                                object_id=str(payment.id),
                                details={
                                    'reference': payment.reference,
                                    'amount': str(payment.amount),
                                    'mpesa_code': mpesa_code or '',
                                    'callback_id': request_id
                                },
                                ip_address=ip_address
                            )
                        except Exception as e:
                            logger.error(f"[Callback:{request_id}] Failed to create audit log: {str(e)}")
                        
                        logger.info(
                            f"[Callback:{request_id}] Payment completed successfully: "
                            f"User={payment.user.id}, Amount={payment.amount}, "
                            f"Reference={reference}, M-Pesa={mpesa_code}"
                        )
                    
                    response_status = 'completed'
                    response_message = 'Payment processed successfully'
                
                elif is_cancelled:
                    payment.status = 'cancelled'
                    payment.metadata['cancelled_at'] = timezone.now().isoformat()
                    payment.save(update_fields=['status', 'metadata', 'updated_at'])
                    
                    logger.info(f"[Callback:{request_id}] Payment cancelled: {reference}")
                    response_status = 'cancelled'
                    response_message = 'Payment was cancelled'
                
                elif is_failed:
                    payment.status = 'failed'
                    payment.failed_at = timezone.now()
                    payment.metadata['failure_reason'] = response_data.get('message', response_data.get('error', 'Payment failed'))
                    payment.save(update_fields=['status', 'failed_at', 'metadata', 'updated_at'])
                    
                    logger.info(f"[Callback:{request_id}] Payment failed: {reference}")
                    response_status = 'failed'
                    response_message = 'Payment failed'
                
                else:
                    # Unknown status - log but don't change
                    logger.warning(f"[Callback:{request_id}] Unknown payment status: {status} for {reference}")
                    payment.metadata['unknown_status'] = {
                        'status': status,
                        'payload': payload
                    }
                    payment.save(update_fields=['metadata', 'updated_at'])
                    
                    response_status = payment.status
                    response_message = 'Callback received with unknown status'
        
        except Exception as e:
            logger.error(
                f"[Callback:{request_id}] Error processing payment: {str(e)}", 
                exc_info=True
            )
            
            # Clear idempotency cache on error to allow retry
            cache.delete(cache_key)
            
            return JsonResponse({
                'success': False,
                'error': 'Error processing payment'
            }, status=500)
        
        # ============================================
        # 6. RETURN SUCCESS RESPONSE
        # ============================================
        return JsonResponse({
            'success': True,
            'status': response_status,
            'message': response_message,
            'reference': payment.reference,
            'transaction_id': payment.id
        })
    
    except Exception as e:
        logger.error(
            f"[Callback:{request_id}] Unhandled callback error: {str(e)}", 
            exc_info=True
        )
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)


# ============================================
# SIMPLIFIED VERSION FOR QUICK FIX
# ============================================

@csrf_exempt
@require_POST
def deposit_success_simple(request):
    """
    Simplified version - use this if the above is too complex
    Maintains backward compatibility with your existing endpoint
    """
    try:
        data = json.loads(request.body)
        response_data = data.get('response', {})
        print(f"[Callback: {response_data}")
        
        # Extract reference (check multiple field names)
        reference = (
            response_data.get("ExternalReference") or 
            response_data.get("external_reference") or
            response_data.get("reference")
        )
        
        # Extract status (check multiple field names)
        status = (
            response_data.get("Status") or 
            response_data.get("status")
        )
        
        if not reference:
            return JsonResponse({'error': 'Missing reference'}, status=400)
        
        # Find transaction
        try:
            payment = Transaction.objects.get(reference=reference)
        except Transaction.DoesNotExist:
            return JsonResponse({'error': 'Transaction not found'}, status=404)
        
        # Update status
        old_status = payment.status
        
        if status and "Success" in status:
            payment.status = "completed"
            payment.completed_at = timezone.now()
            
            # Credit wallet
            try:
                wallet = payment.user.wallet
                wallet.balance += payment.amount
                wallet.total_deposited += payment.amount
                wallet.last_deposit_at = timezone.now()
                wallet.save()
            except Exception as e:
                logger.error(f"Failed to credit wallet: {e}")
        
        elif status and "Cancelled" in status:
            payment.status = "cancelled"
            payment.failed_at = timezone.now()
        
        else:
            payment.status = "failed"
            payment.failed_at = timezone.now()
        
        payment.metadata['callback_data'] = data
        payment.save()
        
        logger.info(f"Deposit callback processed: {reference} - {old_status} -> {payment.status}")
        
        return JsonResponse({
            'success': True,
            'status': payment.status,
            'reference': payment.reference
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal error'}, status=500)