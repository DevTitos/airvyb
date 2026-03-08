from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from django.db import transaction
import json
from datetime import timedelta
import random
import string
from django.core.mail import send_mail
from .models import User, OTP, UserSession, AuditLog
from .forms import (
    UserRegistrationForm, UserLoginForm, EmailVerificationForm,
    PasswordResetRequestForm, PasswordResetForm, ProfileUpdateForm
)
from .utils import send_verification_email, send_sms_verification, log_user_activity
from activation.models import MemberActivation
@csrf_exempt
@require_http_methods(["POST"])
def ajax_register(request):
    """AJAX endpoint for user registration"""
    try:
        data = json.loads(request.body)
        form = UserRegistrationForm(data)
        
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.set_password(form.cleaned_data['password'])
                user.is_active = True
                user.save()
                
                # Generate and send verification code
                code = ''.join(random.choices(string.digits, k=6))
                expires = timezone.now() + timedelta(minutes=10)
                
                OTP.objects.create(
                    user=user,
                    code=code,
                    purpose='verification',
                    expires_at=expires
                )
                
                # Send verification email
                send_verification_email(user.email, code)
                
                # If phone number provided, also send SMS
                if user.phone_number:
                    send_sms_verification(user.phone_number, code)
                
                # Log activity
                log_user_activity(
                    user=user,
                    action='registration_initiated',
                    ip_address=get_client_ip(request),
                    details={'email': user.email}
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Registration successful! Please check your email for verification code.',
                    'user_id': user.id,
                    'requires_verification': True
                })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Registration failed: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def ajax_verify_email(request):
    """AJAX endpoint for email verification"""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        code = data.get('code')
        
        user = get_object_or_404(User, id=user_id)
        
        # Find valid OTP
        otp = OTP.objects.filter(
            user=user,
            code=code,
            purpose='verification',
            is_used=False,
            expires_at__gt=timezone.now()
        ).first()
        
        if otp:
            otp.is_used = True
            otp.save()
            
            user.is_verified = True
            user.save()
            
            # Log activity
            log_user_activity(
                user=user,
                action='email_verified',
                ip_address=get_client_ip(request),
                details={'method': 'code_verification'}
            )
            
            # Auto-login after verification
            login(request, user)

            try:
                activation = MemberActivation.objects.get(user=user)
                
                # Check if membership is active
                if activation.is_active:
                    messages.success(request, f'Welcome back, {user.username}!')
                    return JsonResponse({
                        'success': True,
                        'message': 'Login successful!',
                        'redirect_url': '/dashboard/'
                    })
                #else:
                #    # Has record but not active - send to activation
                #    messages.info(request, 'Please activate your membership to continue.')
                #    return redirect('activation:page')
                    
            except MemberActivation.DoesNotExist:
                # No activation record - create pending record and send to activation
                MemberActivation.objects.create(
                    user=user,
                    status='pending'
                )
                #messages.info(
                #    request, 
                #    'Welcome! You are Enjoying freemium membership.'
                #)
                #return redirect('activation:page')
            
            return JsonResponse({
                'success': True,
                'message': 'Email verified successfully!',
                'redirect_url': '/dashboard/'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid or expired verification code.'
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Verification failed: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def ajax_login(request):
    """AJAX endpoint for user login"""
    try:
        data = json.loads(request.body)
        identifier = data.get('username')
        password = data.get('password')
        
        # Determine if identifier is email or phone
        if '@' in identifier:
            try:
                user = User.objects.get(email=identifier)
            except User.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid credentials'
                }, status=400)
        else:
            # Assume it's a phone number
            try:
                user = User.objects.get(phone_number=identifier)
            except User.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid credentials'
                }, status=400)
        
        # Authenticate user
        user = authenticate(request, username=user.email, password=password)
        
        if user is not None:
            if not user.is_verified:
                # Send new verification code
                code = ''.join(random.choices(string.digits, k=6))
                expires = timezone.now() + timedelta(minutes=10)
                
                OTP.objects.filter(user=user, purpose='verification').delete()
                OTP.objects.create(
                    user=user,
                    code=code,
                    purpose='verification',
                    expires_at=expires
                )
                
                send_verification_email(user.email, code)
                
                return JsonResponse({
                    'success': True,
                    'requires_verification': True,
                    'user_id': user.id,
                    'message': 'Please verify your email first. New code sent.'
                })
            
            # Login successful
            login(request, user)

            # Track session
            UserSession.objects.create(
                user=user,
                session_key=request.session.session_key,
                device_info=get_device_info(request),
                ip_address=get_client_ip(request)
            )
            
            # Log activity
            log_user_activity(
                user=user,
                action='login',
                ip_address=get_client_ip(request),
                details={'method': 'password'}
            )
            
            
            try:
                activation = MemberActivation.objects.get(user=user)
                
                # Check if membership is active
                if activation.is_active:
                    messages.success(request, f'Welcome back, {user.username}!')
                    return JsonResponse({
                        'success': True,
                        'message': 'Login successful!',
                        'redirect_url': '/dashboard/'
                    })
                else:
                    # Has record but not active - send to activation
                    messages.info(request, 'Please activate your membership to continue.')
                    return redirect('activation:page')
                    
            except MemberActivation.DoesNotExist:
                # No activation record - create pending record and send to activation
                MemberActivation.objects.create(
                    user=user,
                    status='pending'
                )
                messages.info(
                    request, 
                    'Welcome! Please activate your membership with a one-time fee of KSH 100.'
                )
                return redirect('activation:page')
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid credentials'
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Login failed: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def ajax_resend_verification(request):
    """AJAX endpoint to resend verification code"""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        user = get_object_or_404(User, id=user_id)
        
        # Generate new code
        code = ''.join(random.choices(string.digits, k=6))
        expires = timezone.now() + timedelta(minutes=10)
        
        # Delete old OTPs
        OTP.objects.filter(user=user, purpose='verification').delete()
        
        # Create new OTP
        OTP.objects.create(
            user=user,
            code=code,
            purpose='verification',
            expires_at=expires
        )
        
        # Send verification email
        send_verification_email(user.email, code)
        
        # If phone number provided, also send SMS
        if user.phone_number:
            send_sms_verification(user.phone_number, code)
        
        return JsonResponse({
            'success': True,
            'message': 'New verification code sent successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Failed to resend code: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def ajax_password_reset_request(request):
    """AJAX endpoint to request password reset"""
    try:
        data = json.loads(request.body)
        identifier = data.get('email_or_phone')
        
        # Find user by email or phone
        if '@' in identifier:
            user = User.objects.filter(email=identifier).first()
        else:
            user = User.objects.filter(phone_number=identifier).first()
        
        if user:
            # Generate reset code
            code = ''.join(random.choices(string.digits, k=6))
            expires = timezone.now() + timedelta(minutes=15)
            
            OTP.objects.filter(user=user, purpose='password_reset').delete()
            OTP.objects.create(
                user=user,
                code=code,
                purpose='password_reset',
                expires_at=expires
            )
            
            # Send reset email
            subject = "Airvyb Password Reset"
            message = f"Your password reset code is: {code}\n\nThis code will expire in 15 minutes."
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            # Log activity
            log_user_activity(
                user=user,
                action='password_reset_requested',
                ip_address=get_client_ip(request),
                details={'method': 'email'}
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Password reset code sent to your email.',
                'user_id': user.id
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'No account found with that email or phone number.'
            }, status=404)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Failed to process request: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def ajax_password_reset_confirm(request):
    """AJAX endpoint to confirm password reset with code"""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        code = data.get('code')
        new_password = data.get('new_password')
        
        user = get_object_or_404(User, id=user_id)
        
        # Verify OTP
        otp = OTP.objects.filter(
            user=user,
            code=code,
            purpose='password_reset',
            is_used=False,
            expires_at__gt=timezone.now()
        ).first()
        
        if otp:
            otp.is_used = True
            otp.save()
            
            # Update password
            user.set_password(new_password)
            user.save()
            
            # Log activity
            log_user_activity(
                user=user,
                action='password_reset_completed',
                ip_address=get_client_ip(request),
                details={'method': 'code_verification'}
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Password reset successful! You can now login.',
                'redirect_url': '/login/'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid or expired reset code.'
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Password reset failed: {str(e)}'
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def ajax_logout(request):
    """AJAX endpoint for logout"""
    try:
        # Log activity
        log_user_activity(
            user=request.user,
            action='logout',
            ip_address=get_client_ip(request),
            details={'method': 'manual'}
        )
        
        logout(request)
        
        return JsonResponse({
            'success': True,
            'message': 'Logged out successfully',
            'redirect_url': '/'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Logout failed: {str(e)}'
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["GET"])
def ajax_get_profile(request):
    """AJAX endpoint to get user profile"""
    try:
        user = request.user
        profile_data = {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number,
            'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
            'country': user.country,
            'county': user.county,
            'is_verified': user.is_verified,
            'is_youth': user.is_youth,
            'age_group': user.age_group,
            'profile_picture': user.profile_picture.url if user.profile_picture else None,
            'date_joined': user.date_joined.isoformat(),
        }
        
        return JsonResponse({
            'success': True,
            'profile': profile_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Failed to get profile: {str(e)}'
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def ajax_update_profile(request):
    """AJAX endpoint to update user profile"""
    try:
        data = request.POST.copy()
        files = request.FILES
        
        form = ProfileUpdateForm(data, files, instance=request.user)
        
        if form.is_valid():
            user = form.save()
            
            # Log activity
            log_user_activity(
                user=user,
                action='profile_updated',
                ip_address=get_client_ip(request),
                details={'fields_updated': list(form.changed_data)}
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Profile updated successfully!',
                'profile_picture': user.profile_picture.url if user.profile_picture else None
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Failed to update profile: {str(e)}'
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def ajax_change_password(request):
    """AJAX endpoint to change password"""
    try:
        data = json.loads(request.body)
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        user = request.user
        
        # Verify current password
        if not user.check_password(current_password):
            return JsonResponse({
                'success': False,
                'message': 'Current password is incorrect.'
            }, status=400)
        
        # Validate new password
        if len(new_password) < 8:
            return JsonResponse({
                'success': False,
                'message': 'Password must be at least 8 characters long.'
            }, status=400)
        
        # Update password
        user.set_password(new_password)
        user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, user)
        
        # Log activity
        log_user_activity(
            user=user,
            action='password_changed',
            ip_address=get_client_ip(request),
            details={'method': 'manual'}
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Password changed successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Failed to change password: {str(e)}'
        }, status=500)

# Template Views for Authentication Pages

def register_view(request):
    """Render registration page"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'auth/register.html')

def login_view(request):
    """Render login page"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'auth/login.html')

def verify_email_view(request, user_id=None):
    """Render email verification page"""
    return render(request, 'auth/verify_email.html', {'user_id': user_id})

def password_reset_request_view(request):
    """Render password reset request page"""
    return render(request, 'auth/password_reset_request.html')

def password_reset_confirm_view(request, user_id=None):
    """Render password reset confirmation page"""
    return render(request, 'auth/password_reset_confirm.html', {'user_id': user_id})

@login_required
def profile_view(request):
    """Render profile page"""
    return render(request, 'auth/profile.html')

@login_required
def dashboard_view(request):
    """Render dashboard page"""
    return render(request, 'dashboard.html')

# Utility functions

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_device_info(request):
    """Extract device information from request"""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    # Simple parsing - in production, use a proper user agent parser
    return {
        'user_agent': user_agent,
        'browser': 'Unknown',  # Parse from user_agent in production
        'platform': 'Unknown',  # Parse from user_agent in production
    }