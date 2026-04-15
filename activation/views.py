from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db import transaction as db_transaction
from django.conf import settings
from decimal import Decimal
import json
import re
import requests
import logging
from django.urls import reverse

from .models import MemberActivation, MembershipBenefit, ActivationPromo
from finance.models import Wallet, Transaction
from intasend import APIService

logger = logging.getLogger(__name__)

intasend_service = APIService(
    token=settings.INTASEND_TOKEN,
    publishable_key=settings.INTASEND_PUBLISHABLE_KEY
)
# ============================================
# ACTIVATION PAGE
# ============================================

@login_required
@require_GET
def activation_page(request):
    """Member activation page"""
    user = request.user
    
    # Check if user already has activation
    activation, created = MemberActivation.objects.get_or_create(
        user=user,
        defaults={
            'status': 'pending'
        }
    )
    
    # Get membership benefits
    benefits = MembershipBenefit.objects.filter(is_active=True)
    
    # Get user wallet for balance check
    wallet = None
    try:
        wallet = Wallet.objects.get(user=user)
    except Wallet.DoesNotExist:
        pass
    
    # Check if already active
    is_active = activation.is_active
    
    # Get promo if any
    promo_code = request.GET.get('promo')
    promo = None
    discount = 0
    final_amount = Decimal('100.00')
    
    if promo_code:
        try:
            promo = ActivationPromo.objects.get(code=promo_code.upper())
            if promo.is_valid:
                discount = promo.calculate_discount(final_amount)
                final_amount = final_amount - discount
        except ActivationPromo.DoesNotExist:
            pass
    
    context = {
        'activation': activation,
        'benefits': benefits,
        'wallet': wallet,
        'is_active': is_active,
        'promo': promo,
        'discount': discount,
        'final_amount': final_amount,
        'membership_fee': Decimal('100.00'),
        'page_title': 'Activate Membership' if not is_active else 'Membership Active',
    }
    
    return render(request, 'activation/activation_page.html', context)


# ============================================
# INITIATE ACTIVATION PAYMENT
# ============================================

@login_required
@require_POST
def initiate_activation(request):
    """Initiate membership fee payment"""
    user = request.user
    
    try:
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        # Get payment details
        payment_method = data.get('payment_method', 'mpesa')
        phone = data.get('phone', '').strip()
        promo_code = data.get('promo_code', '').strip().upper()
        
        # Get or create activation record
        activation, created = MemberActivation.objects.get_or_create(
            user=user,
            defaults={
                'status': 'pending',
                'amount': Decimal('100.00')
            }
        )
        
        # Check if already active
        if activation.is_active:
            return JsonResponse({
                'success': False,
                'error': 'Your membership is already active.',
                'redirect_url': reverse('activation:page')
            }, status=400)
        
        # Calculate final amount with promo
        amount = Decimal('100.00')
        discount = Decimal('0.00')
        promo = None
        
        if promo_code:
            try:
                promo = ActivationPromo.objects.get(code=promo_code)
                if promo.is_valid:
                    discount = promo.calculate_discount(amount)
                    amount = amount - discount
                    
                    # Increment promo usage
                    promo.current_uses += 1
                    promo.save()
            except ActivationPromo.DoesNotExist:
                pass
        
        # Process based on payment method
        if payment_method == 'wallet':
            return process_wallet_activation(request, user, activation, amount, discount, promo)
        else:  # M-Pesa
            return process_mpesa_activation(request, user, activation, phone, amount, discount, promo)
    
    except Exception as e:
        logger.error(f"Activation initiation error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please try again.'
        }, status=500)


def process_wallet_activation(request, user, activation, amount, discount, promo):
    """Process activation payment via wallet balance"""
    try:
        with db_transaction.atomic():
            # Get user wallet
            wallet = Wallet.objects.select_for_update().get(user=user)
            
            # Check sufficient balance
            if wallet.available_balance < amount:
                return JsonResponse({
                    'success': False,
                    'error': f'Insufficient wallet balance. Need Ksh {amount:,.0f}, Available: Ksh {wallet.available_balance:,.0f}',
                    'redirect_url': reverse('finance:deposit')
                }, status=400)
            
            # Generate reference
            reference = f"ACT-{timezone.now().strftime('%Y%m%d%H%M%S')}-{user.id}"
            
            # Create transaction
            transaction = Transaction.objects.create(
                user=user,
                transaction_type='fee',
                payment_method='wallet',
                reference=reference,
                amount=amount,
                fee=0,
                net_amount=amount,
                balance_before=wallet.balance,
                balance_after=wallet.balance - amount,
                description=f"Membership activation fee payment",
                status='completed',
                completed_at=timezone.now(),
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Update wallet
            wallet.balance -= amount
            wallet.save()
            
            # Update activation record
            activation.status = 'active'
            activation.payment_method = 'wallet'
            activation.amount = amount
            activation.transaction = transaction
            activation.activated_at = timezone.now()
            activation.expires_at = timezone.now() + timezone.timedelta(days=365)
            activation.metadata = {
                'payment_method': 'wallet',
                'discount_applied': float(discount),
                'promo_code': promo.code if promo else None,
                'balance_before': float(transaction.balance_before),
                'balance_after': float(transaction.balance_after)
            }
            activation.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Membership activated successfully!',
                'activation': {
                    'status': activation.status,
                    'activated_at': activation.activated_at,
                    'expires_at': activation.expires_at,
                    'reference': activation.reference
                },
                'transaction': {
                    'id': transaction.id,
                    'reference': transaction.reference,
                    'amount': float(transaction.amount),
                    'balance_after': float(wallet.balance)
                }
            })
    
    except Wallet.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'You need to create a wallet first. Please make a deposit.',
            'redirect_url': reverse('finance:deposit')
        }, status=400)
    
    except Exception as e:
        logger.error(f"Wallet activation error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to process wallet payment.'
        }, status=500)


def process_mpesa_activation(request, user, activation, phone, amount, discount, promo):
    """Process activation payment via M-Pesa using IntaSend"""
    
    # Validate phone number
    phone = clean_phone_number(phone)
    if not phone:
        return JsonResponse({
            'success': False,
            'error': 'Please enter a valid M-Pesa number (07XXXXXXXX)'
        }, status=400)
    
    # Format phone for IntaSend (ensure it starts with 254)
    if phone.startswith('0'):
        intasend_phone = f"254{phone[1:]}"
    elif phone.startswith('7'):
        intasend_phone = f"254{phone}"
    else:
        intasend_phone = phone
    
    # Generate reference
    reference = f"ACT-{timezone.now().strftime('%Y%m%d%H%M%S')}-{user.id}"
    
    # Update activation record
    activation.phone_number = phone
    activation.payment_method = 'mpesa'
    activation.amount = amount
    activation.metadata['discount_applied'] = float(discount)
    activation.metadata['promo_code'] = promo.code if promo else None
    activation.save()
    
    try:
        # Initiate STK Push with IntaSend
        response = intasend_service.collect.mpesa_stk_push(
            phone_number=int(intasend_phone),
            email=user.email,
            amount=int(amount),
            narrative=f"Membership Activation - {user.username}"
        )
        
        # Check if the request was successful
        if response and response.get('id') and response.get('invoice'):
            payment_id = response.get('id')
            invoice_id = response['invoice']['invoice_id']
            # Create pending transaction
            transaction = Transaction.objects.create(
                user=user,
                transaction_type='fee',
                payment_method='mpesa',
                reference=reference,
                amount=amount,
                fee=0,
                net_amount=amount,
                balance_before=0,
                balance_after=0,
                phone_number=phone,
                description=f"Membership activation fee payment via M-Pesa",
                status='processing',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={
                    'activation_id': activation.id,
                    'intasend_payment_id': payment_id,
                    'intasend_invoice_id': invoice_id,
                    'api_response': response
                }
            )
            # Link transaction to activation
            activation.transaction = transaction
            activation.status = 'processing'
            activation.reference = reference
            activation.metadata['intasend_invoice_id'] = invoice_id
            activation.save()
            
            return JsonResponse({
                'success': True,
                'message': 'STK push initiated! Check your phone to complete payment.',
                'transaction': {
                    'id': transaction.id,
                    'reference': transaction.reference,
                    'amount': float(transaction.amount),
                    'phone': transaction.phone_number,
                    'status': transaction.status,
                    'invoice_id': invoice_id
                }
            })
        else:
            error_message = response.get('error', 'Failed to initiate M-Pesa payment')
            logger.error(f"IntaSend STK Push failed: {response}")
            
            return JsonResponse({
                'success': False,
                'error': f'Failed to initiate M-Pesa payment: {error_message}'
            }, status=400)
    
    except Exception as e:
        logger.error(f"IntaSend activation error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while processing your payment.'
        }, status=500)


# ============================================
# CHECK ACTIVATION PAYMENT STATUS (UPDATED FOR INTASEND)
# ============================================

@login_required
@require_GET
def check_activation_status(request):
    """
    Check current activation status and optionally update from IntaSend
    This function handles both:
    1. Checking the status of a pending payment
    2. Getting the current activation status for a user
    """
    user = request.user
    invoice_id = request.GET.get('invoice_id')
    
    try:
        # Get user's activation
        activation = MemberActivation.objects.get(user=user)
        
        # If invoice_id is provided and payment is still processing, check with IntaSend
        if invoice_id and activation.status in ['processing', 'pending']:
            try:
                # Check status with IntaSend
                status_response = intasend_service.collect.status(invoice_id=invoice_id)
                
                if status_response and 'invoice' in status_response:
                    invoice = status_response['invoice']
                    state = invoice.get('state')
                    failed_reason = invoice.get('failed_reason')
                    
                    # Map IntaSend states to your statuses
                    status_mapping = {
                        'PENDING': 'processing',
                        'COMPLETE': 'active',  # Payment complete, activate membership
                        'FAILED': 'failed',
                        'PROCESSING': 'processing'
                    }
                    
                    new_status = status_mapping.get(state, activation.status)
                    
                    # If status changed, update database
                    if new_status != activation.status:
                        with db_transaction.atomic():
                            # Update activation status
                            activation.status = new_status
                            
                            # If transaction exists, update it
                            if activation.transaction:
                                transaction_status_mapping = {
                                    'PENDING': 'processing',
                                    'COMPLETE': 'completed',
                                    'FAILED': 'failed',
                                    'PROCESSING': 'processing'
                                }
                                activation.transaction.status = transaction_status_mapping.get(
                                    state, activation.transaction.status
                                )
                                
                                if state == 'COMPLETE':
                                    activation.transaction.completed_at = timezone.now()
                                    activation.activated_at = timezone.now()
                                    activation.expires_at = timezone.now() + timezone.timedelta(days=365)
                                    activation.mpesa_code = invoice.get('mpesa_receipt_number')
                                
                                activation.transaction.save()
                            
                            # Update metadata with status check
                            if 'status_checks' not in activation.metadata:
                                activation.metadata['status_checks'] = []
                            
                            activation.metadata['status_checks'].append({
                                'timestamp': timezone.now().isoformat(),
                                'state': state,
                                'failed_reason': failed_reason
                            })
                            activation.save()
                            
                            logger.info(f"Activation status updated for {user.email}: {activation.status}")
                    
                    # If payment failed, include reason
                    if state == 'FAILED':
                        return JsonResponse({
                            'success': True,
                            'status': activation.status,
                            'payment_status': state,
                            'failed_reason': failed_reason,
                            'is_active': activation.is_active,
                            'activated_at': activation.activated_at,
                            'expires_at': activation.expires_at,
                            'days_remaining': activation.days_remaining,
                            'progress': activation.progress_percentage,
                            'reference': activation.reference,
                            'invoice_id': invoice_id
                        })
            
            except Exception as e:
                logger.error(f"IntaSend status check error: {str(e)}", exc_info=True)
                # Continue with existing status if IntaSend check fails
        
        # Return current activation status
        return JsonResponse({
            'success': True,
            'status': activation.status,
            'is_active': activation.is_active,
            'activated_at': activation.activated_at,
            'expires_at': activation.expires_at,
            'days_remaining': activation.days_remaining,
            'progress': activation.progress_percentage,
            'reference': activation.reference,
            'invoice_id': activation.metadata.get('intasend_invoice_id'),
            'payment_method': activation.payment_method,
            'amount': float(activation.amount) if activation.amount else None
        })
    
    except MemberActivation.DoesNotExist:
        return JsonResponse({
            'success': True,
            'status': 'none',
            'is_active': False
        })


# ============================================
# INTASEND WEBHOOK/CALLBACK HANDLER
# ============================================

@csrf_exempt
@require_POST
def activation_callback(request):
    """
    Handle IntaSend payment callback/webhook for activation
    This replaces the old PayHero callback
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
            return JsonResponse({'error': 'Missing invoice_id'}, status=400)
        
        # Find activation by invoice_id in metadata
        try:
            activation = MemberActivation.objects.get(
                metadata__intasend_invoice_id=invoice_id
            )
        except MemberActivation.DoesNotExist:
            # Try to find by searching in metadata JSON
            activations = MemberActivation.objects.filter(
                metadata__has_key='intasend_invoice_id'
            )
            activation = None
            for act in activations:
                if act.metadata.get('intasend_invoice_id') == invoice_id:
                    activation = act
                    break
            
            if not activation:
                logger.error(f"Activation not found for invoice_id: {invoice_id}")
                return JsonResponse({'error': 'Activation not found'}, status=404)
        
        # Process based on state
        with db_transaction.atomic():
            # Map IntaSend states to your statuses
            if state == 'COMPLETE':
                # Get or create transaction
                transaction = activation.transaction
                if not transaction:
                    transaction = Transaction.objects.create(
                        user=activation.user,
                        transaction_type='fee',
                        payment_method='mpesa',
                        reference=activation.reference,
                        amount=activation.amount,
                        fee=0,
                        net_amount=activation.amount,
                        balance_before=0,
                        balance_after=0,
                        phone_number=activation.phone_number,
                        description="Membership activation fee payment",
                        status='completed',
                        completed_at=timezone.now(),
                        mpesa_code=mpesa_receipt,
                        metadata={
                            'callback_data': payload,
                            'intasend_invoice_id': invoice_id
                        }
                    )
                else:
                    transaction.status = 'completed'
                    transaction.completed_at = timezone.now()
                    transaction.mpesa_code = mpesa_receipt
                    transaction.metadata['callback_data'] = payload
                    transaction.metadata['intasend_invoice_id'] = invoice_id
                    transaction.save()
                
                # Activate membership
                activation.status = 'active'
                activation.transaction = transaction
                activation.activated_at = timezone.now()
                activation.expires_at = timezone.now() + timezone.timedelta(days=365)
                activation.mpesa_code = mpesa_receipt
                activation.metadata['callback_data'] = payload
                activation.metadata['intasend_invoice_id'] = invoice_id
                activation.save()
                
                logger.info(f"Membership activated for {activation.user.email} via IntaSend")
                
                return JsonResponse({'success': True, 'status': 'activated'})
            
            elif state == 'FAILED':
                activation.status = 'failed'
                activation.metadata['failed_reason'] = failed_reason
                activation.metadata['callback_data'] = payload
                activation.save()
                
                if activation.transaction:
                    activation.transaction.status = 'failed'
                    activation.transaction.metadata['failed_reason'] = failed_reason
                    activation.transaction.save()
                
                logger.info(f"Payment failed for {activation.user.email}: {failed_reason}")
                return JsonResponse({'success': True, 'status': 'failed'})
            
            elif state == 'PENDING':
                activation.status = 'processing'
                activation.metadata['callback_data'] = payload
                activation.save()
                
                return JsonResponse({'success': True, 'status': 'processing'})
            
            else:
                # Other states (PROCESSING, etc.)
                activation.metadata['callback_data'] = payload
                activation.save()
                return JsonResponse({'success': True, 'status': state.lower()})
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in callback")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    except Exception as e:
        logger.error(f"Activation callback error: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


# ============================================
# LEGACY PAYHERO CALLBACK (KEPT FOR BACKWARD COMPATIBILITY)
# ============================================

@csrf_exempt
@require_POST
def legacy_activation_callback(request):
    """
    Legacy callback handler for PayHero (kept for backward compatibility)
    This can be removed after migration is complete
    """
    try:
        payload = json.loads(request.body)
        response_data = payload.get('response', payload)
        
        reference = (
            response_data.get('ExternalReference') or
            response_data.get('external_reference') or
            response_data.get('reference')
        )
        
        if not reference:
            return JsonResponse({'error': 'Missing reference'}, status=400)
        
        # Try to find activation
        try:
            activation = MemberActivation.objects.get(reference=reference)
        except MemberActivation.DoesNotExist:
            try:
                transaction = Transaction.objects.get(reference=reference)
                activation = transaction.activation.first()
            except (Transaction.DoesNotExist, AttributeError):
                return JsonResponse({'error': 'Activation not found'}, status=404)
        
        # Extract status
        status = response_data.get('Status') or response_data.get('status')
        mpesa_code = response_data.get('MpesaReceiptNumber') or response_data.get('mpesa_code')
        
        # Process based on status
        if status and 'Success' in status:
            with db_transaction.atomic():
                transaction = activation.transaction
                if not transaction:
                    transaction = Transaction.objects.create(
                        user=activation.user,
                        transaction_type='fee',
                        payment_method='mpesa',
                        reference=reference,
                        amount=activation.amount,
                        fee=0,
                        net_amount=activation.amount,
                        balance_before=0,
                        balance_after=0,
                        phone_number=activation.phone_number,
                        description="Membership activation fee payment",
                        status='completed',
                        completed_at=timezone.now(),
                        mpesa_code=mpesa_code,
                        metadata={'callback_data': payload}
                    )
                else:
                    transaction.status = 'completed'
                    transaction.completed_at = timezone.now()
                    transaction.mpesa_code = mpesa_code
                    transaction.metadata['callback_data'] = payload
                    transaction.save()
                
                activation.status = 'active'
                activation.transaction = transaction
                activation.activated_at = timezone.now()
                activation.expires_at = timezone.now() + timezone.timedelta(days=365)
                activation.mpesa_code = mpesa_code
                activation.metadata['callback_data'] = payload
                activation.save()
                
                return JsonResponse({'success': True})
        
        elif status and 'Cancelled' in status:
            activation.status = 'cancelled'
            activation.save()
            return JsonResponse({'success': True})
        
        else:
            activation.status = 'failed'
            activation.save()
            return JsonResponse({'success': True})
    
    except Exception as e:
        logger.error(f"Legacy activation callback error: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)

# ============================================
# VERIFY PROMO CODE
# ============================================

@login_required
@require_GET
def verify_promo(request):
    """Verify promo code validity"""
    code = request.GET.get('code', '').strip().upper()
    
    if not code:
        return JsonResponse({
            'success': False,
            'error': 'Please enter a promo code'
        }, status=400)
    
    try:
        promo = ActivationPromo.objects.get(code=code)
        
        if promo.is_valid:
            discount = promo.calculate_discount(Decimal('100.00'))
            final_amount = Decimal('100.00') - discount
            
            return JsonResponse({
                'success': True,
                'code': promo.code,
                'discount_percent': promo.discount_percent,
                'discount_amount': float(discount),
                'final_amount': float(final_amount),
                'description': promo.description
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'This promo code is invalid or expired'
            }, status=400)
    
    except ActivationPromo.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Invalid promo code'
        }, status=400)


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