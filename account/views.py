# views.py
import json
import random
import string
from datetime import timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings

from .models import User, OTP, UserSession, AuditLog, HederaTransaction, TokenBalance
from .forms import UserRegistrationForm, ProfileUpdateForm
from .utils import send_verification_email, send_sms_verification
from .hedera import HederaService  # Updated Hedera service

#===============================================================================
# CONSTANTS
#===============================================================================

OTP_EXPIRY_MINUTES = 10
PASSWORD_RESET_EXPIRY_MINUTES = 15
OTP_LENGTH = 6

#===============================================================================
# DECORATORS
#===============================================================================

def ajax_error_handler(view_func):
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return wrapper

#===============================================================================
# UTILITY FUNCTIONS
#===============================================================================

def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')

def generate_otp():
    return ''.join(random.choices(string.digits, k=OTP_LENGTH))

def create_otp(user, purpose):
    code = generate_otp()
    expires = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    OTP.objects.filter(user=user, purpose=purpose).delete()
    return OTP.objects.create(user=user, code=code, purpose=purpose, expires_at=expires)

def verify_otp(user, code, purpose):
    return OTP.objects.filter(
        user=user, code=code, purpose=purpose, 
        is_used=False, expires_at__gt=timezone.now()
    ).first()

def get_user_by_identifier(identifier):
    if '@' in identifier:
        return User.objects.filter(email=identifier).first()
    return User.objects.filter(phone_number=identifier).first()

#===============================================================================
# HEDERA VIEWS
#===============================================================================

@login_required
@require_http_methods(["GET"])
def hedera_account_status(request):
    """Get Hedera account status and balance"""
    user = request.user
    
    # Update balance if stale (older than 5 minutes)
    if user.has_hedera_account and (not user.hedera_balance_updated_at or 
       (timezone.now() - user.hedera_balance_updated_at) > timedelta(minutes=5)):
        try:
            balance = HederaService.get_account_balance(user.hedera_account_id)
            user.hedera_balance = balance
            user.hedera_balance_updated_at = timezone.now()
            user.save(update_fields=['hedera_balance', 'hedera_balance_updated_at'])
        except Exception:
            pass  # Use cached balance if update fails
    
    return JsonResponse({
        'success': True,
        'has_account': user.has_hedera_account,
        'account_id': user.hedera_account_id,
        'status': user.hedera_account_status,
        'balance': str(user.hedera_balance),
        'balance_display': f"{user.hedera_balance:.8f} ℏ".rstrip('0').rstrip('.') + ' ℏ',
        'explorer_url': f"https://hashscan.io/testnet/account/{user.hedera_account_id}" if user.hedera_account_id else None
    })

@login_required
@require_http_methods(["POST"])
@ajax_error_handler
def hedera_create_account(request):
    """Create Hedera account for user"""
    user = request.user
    
    if user.has_hedera_account:
        return JsonResponse({
            'success': False,
            'message': 'Hedera account already exists'
        }, status=400)
    
    with transaction.atomic():
        # Create Hedera account using hiero_sdk_python
        account_data = HederaService.create_account(user.full_name or user.email)
        
        if not account_data:
            return JsonResponse({
                'success': False,
                'message': 'Failed to create Hedera account'
            }, status=500)
        
        # Update user with Hedera account info
        user.hedera_account_id = account_data['account_id']
        user.hedera_public_key = account_data['public_key']
        user.hedera_private_key_encrypted = HederaService.encrypt_private_key(account_data['private_key'])
        user.hedera_account_status = 'active'
        user.hedera_balance = Decimal('1')  # Initial balance from account creation
        user.hedera_balance_updated_at = timezone.now()
        user.save()
        
        # Log activity
        AuditLog.objects.create(
            user=user,
            action='hedera_account_created',
            details={'account_id': account_data['account_id']},
            ip_address=get_client_ip(request)
        )
    
    return JsonResponse({
        'success': True,
        'message': 'Hedera account created successfully',
        'account_id': user.hedera_account_id,
        'balance': str(user.hedera_balance)
    })


#===============================================================================
# AUTH VIEWS
#===============================================================================

@csrf_exempt
@require_http_methods(["POST"])
@ajax_error_handler
def ajax_register(request):
    data = json.loads(request.body)
    form = UserRegistrationForm(data)
    
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    
    with transaction.atomic():
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.save()
        
        # Create OTP
        create_otp(user, 'verification')
        
        # Send verification
        send_verification_email(user.email, user.otps.first().code)
        
        if user.phone_number:
            send_sms_verification(user.phone_number, user.otps.first().code)
        
        # Log
        AuditLog.objects.create(
            user=user,
            action='registration',
            details={'email': user.email},
            ip_address=get_client_ip(request)
        )
    
    return JsonResponse({
        'success': True,
        'message': 'Registration successful! Check email for verification.',
        'user_id': user.id,
        'requires_verification': True
    })

# views.py - Updated streamlined flow

@csrf_exempt
@require_http_methods(["POST"])
@ajax_error_handler
def ajax_verify_email(request):
    data = json.loads(request.body)
    user = get_object_or_404(User, id=data.get('user_id'))
    
    otp = verify_otp(user, data.get('code'), 'verification')
    
    if not otp:
        return JsonResponse({'success': False, 'message': 'Invalid or expired code'}, status=400)
    
    otp.is_used = True
    otp.save()
    
    user.is_verified = True
    user.save()
    
    # Auto-create Hedera wallet in background if needed
    if not user.has_hedera_account:
        try:
            account_data = HederaService.create_account(user.email)
            if account_data:
                user.hedera_account_id = account_data['account_id']
                user.hedera_public_key = account_data['public_key']
                user.hedera_private_key_encrypted = HederaService.encrypt_private_key(account_data['private_key'])
                user.hedera_account_status = 'active'
                user.save()
                
                AuditLog.objects.create(
                    user=user,
                    action='hedera_wallet_created',
                    details={'account_id': account_data['account_id']},
                    ip_address=get_client_ip(request)
                )
        except Exception as e:
            # Log error but don't block user
            AuditLog.objects.create(
                user=user,
                action='hedera_wallet_creation_failed',
                details={'error': str(e)},
                ip_address=get_client_ip(request)
            )
    
    # Auto-login after verification
    login(request, user)
    
    return JsonResponse({
        'success': True,
        'message': 'Email verified successfully!',
        'redirect_url': '/dashboard/'
    })

@csrf_exempt
@require_http_methods(["POST"])
@ajax_error_handler
def ajax_login(request):
    data = json.loads(request.body)
    identifier = data.get('username')
    password = data.get('password')
    
    user = get_user_by_identifier(identifier)
    if not user:
        return JsonResponse({'success': False, 'message': 'Invalid credentials'}, status=400)
    
    user = authenticate(request, username=user.email, password=password)
    if not user:
        return JsonResponse({'success': False, 'message': 'Invalid credentials'}, status=400)
    
    if not user.is_verified:
        create_otp(user, 'verification')
        send_verification_email(user.email, user.otps.first().code)
        return JsonResponse({
            'success': True,
            'requires_verification': True,
            'user_id': user.id,
            'message': 'Please verify your email first. New code sent.'
        })
    
    # Auto-create Hedera wallet in background if needed
    if not user.has_hedera_account:
        try:
            account_data = HederaService.create_account(user.email)
            if account_data:
                user.hedera_account_id = account_data['account_id']
                user.hedera_public_key = account_data['public_key']
                user.hedera_private_key_encrypted = HederaService.encrypt_private_key(account_data['private_key'])
                user.hedera_account_status = 'active'
                user.save()
                
                AuditLog.objects.create(
                    user=user,
                    action='hedera_wallet_created',
                    details={'account_id': account_data['account_id']},
                    ip_address=get_client_ip(request)
                )
        except Exception as e:
            # Log error but don't block login
            AuditLog.objects.create(
                user=user,
                action='hedera_wallet_creation_failed',
                details={'error': str(e)},
                ip_address=get_client_ip(request)
            )
    
    # Complete login
    login(request, user)
    
    # Track session
    UserSession.objects.create(
        user=user,
        session_key=request.session.session_key,
        ip_address=get_client_ip(request)
    )
    
    AuditLog.objects.create(
        user=user,
        action='login',
        details={},
        ip_address=get_client_ip(request)
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Login successful',
        'redirect_url': '/dashboard/'
    })

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def ajax_logout(request):
    AuditLog.objects.create(
        user=request.user,
        action='logout',
        details={},
        ip_address=get_client_ip(request)
    )
    logout(request)
    return JsonResponse({'success': True, 'message': 'Logged out', 'redirect_url': '/'})

@csrf_exempt
@require_http_methods(["POST"])
@ajax_error_handler
def ajax_password_reset_request(request):
    data = json.loads(request.body)
    user = get_user_by_identifier(data.get('email_or_phone'))
    
    if not user:
        return JsonResponse({'success': False, 'message': 'No account found'}, status=404)
    
    create_otp(user, 'password_reset')
    send_mail(
        "Password Reset",
        f"Your reset code is: {user.otps.first().code}\n\nValid for 15 minutes.",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    
    AuditLog.objects.create(
        user=user,
        action='password_reset_requested',
        details={},
        ip_address=get_client_ip(request)
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Reset code sent to your email',
        'user_id': user.id
    })

@csrf_exempt
@require_http_methods(["POST"])
@ajax_error_handler
def ajax_password_reset_confirm(request):
    data = json.loads(request.body)
    user = get_object_or_404(User, id=data.get('user_id'))
    
    otp = verify_otp(user, data.get('code'), 'password_reset')
    if not otp:
        return JsonResponse({'success': False, 'message': 'Invalid or expired code'}, status=400)
    
    otp.is_used = True
    otp.save()
    
    user.set_password(data.get('new_password'))
    user.save()
    
    AuditLog.objects.create(
        user=user,
        action='password_reset_completed',
        details={},
        ip_address=get_client_ip(request)
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Password reset successful',
        'redirect_url': '/login/'
    })

#===============================================================================
# PROFILE VIEWS
#===============================================================================

@login_required
@require_http_methods(["GET"])
def ajax_get_profile(request):
    user = request.user
    return JsonResponse({
        'success': True,
        'profile': {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,
            'phone_number': user.phone_number,
            'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
            'country': user.country,
            'county': user.county,
            'is_verified': user.is_verified,
            'profile_picture': user.profile_picture.url if user.profile_picture else None,
        }
    })

@login_required
@csrf_exempt
@require_http_methods(["POST"])
@ajax_error_handler
def ajax_update_profile(request):
    form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
    
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    
    user = form.save()
    
    AuditLog.objects.create(
        user=user,
        action='profile_updated',
        details={'fields': list(form.changed_data)},
        ip_address=get_client_ip(request)
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Profile updated successfully'
    })

@login_required
@csrf_exempt
@require_http_methods(["POST"])
@ajax_error_handler
def ajax_change_password(request):
    data = json.loads(request.body)
    user = request.user
    
    if not user.check_password(data.get('current_password')):
        return JsonResponse({'success': False, 'message': 'Current password incorrect'}, status=400)
    
    new_password = data.get('new_password')
    if len(new_password) < 8:
        return JsonResponse({'success': False, 'message': 'Password must be at least 8 characters'}, status=400)
    
    user.set_password(new_password)
    user.save()
    update_session_auth_hash(request, user)
    
    AuditLog.objects.create(
        user=user,
        action='password_changed',
        details={},
        ip_address=get_client_ip(request)
    )
    
    return JsonResponse({'success': True, 'message': 'Password changed successfully'})


# Add this to your views.py in the AUTH VIEWS section (after ajax_verify_email)

@csrf_exempt
@require_http_methods(["POST"])
@ajax_error_handler
def ajax_resend_verification(request):
    """Resend verification code"""
    data = json.loads(request.body)
    user = get_object_or_404(User, id=data.get('user_id'))
    
    # Create new OTP
    otp = create_otp(user, 'verification')
    
    # Send verification email
    send_verification_email(user.email, otp.code)
    
    if user.phone_number:
        send_sms_verification(user.phone_number, otp.code)
    
    # Log
    AuditLog.objects.create(
        user=user,
        action='verification_resent',
        details={},
        ip_address=get_client_ip(request)
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Verification code resent successfully'
    })

#===============================================================================
# TEMPLATE VIEWS
#===============================================================================

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'auth/register.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'auth/login.html')

def verify_email_view(request, user_id=None):
    return render(request, 'auth/verify_email.html', {'user_id': user_id})

def password_reset_request_view(request):
    return render(request, 'auth/password_reset_request.html')

def password_reset_confirm_view(request, user_id=None):
    return render(request, 'auth/password_reset_confirm.html', {'user_id': user_id})

@login_required
def profile_view(request):
    return render(request, 'auth/profile.html')