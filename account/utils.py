from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import AuditLog
import requests

def send_verification_email(email, code):
    """Send verification email"""
    subject = "Verify Your Airvyb Account"
    message = f"""
    Welcome to Airvyb!
    
    Your verification code is: {code}
    
    This code will expire in 10 minutes.
    
    If you didn't create an account, please ignore this email.
    
    Best regards,
    The Airvyb Team
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )

def send_sms_verification(phone_number, code):
    """Send SMS verification (placeholder - integrate with SMS gateway)"""
    # Example: Integrate with Africa's Talking, Twilio, etc.
    # This is a placeholder function
    try:
        # Example with Africa's Talking
        # username = settings.AFRICASTALKING_USERNAME
        # api_key = settings.AFRICASTALKING_API_KEY
        # africastalking.initialize(username, api_key)
        # sms = africastalking.SMS
        # response = sms.send(f"Your Airvyb verification code: {code}", [phone_number])
        pass
    except Exception as e:
        # Log SMS failure but don't block registration
        print(f"SMS sending failed: {e}")

def log_user_activity(user, action, ip_address=None, details=None):
    """Log user activity for audit trail"""
    AuditLog.objects.create(
        user=user if user.is_authenticated else None,
        action=action,
        details=details or {},
        ip_address=ip_address,
        user_agent=''  # Can be extracted from request if available
    )

def validate_youth_age(date_of_birth):
    """Validate that user is within youth age (18-35)"""
    if not date_of_birth:
        return False
    
    age = (timezone.now().date() - date_of_birth).days // 365
    return 18 <= age <= 35