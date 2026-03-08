from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import AuditLog, Notification
import uuid
import random
import string
from datetime import datetime
from finance.models import Transaction

def generate_transaction_reference():
    """Generate a unique transaction reference"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TXN-{timestamp}-{random_chars}"

def generate_investment_reference():
    """Generate a unique investment reference"""
    return f"INV-{uuid.uuid4().hex[:12].upper()}"

def log_audit(user, action, model_name, object_id=None, details=None, request=None):
    """Log system audit trail"""
    audit_log = AuditLog(
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        details=details or {},
    )
    
    if request:
        audit_log.ip_address = get_client_ip(request)
        audit_log.user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    audit_log.save()
    return audit_log

def create_transaction(user, amount, transaction_type, investment=None, 
                      dividend=None, description='', metadata=None, status='pending'):
    """Create a transaction record"""
    # Get current balance (simplified - in real app, get from wallet)
    current_balance = 0  # Placeholder
    
    transaction = Transaction(
        user=user,
        transaction_type=transaction_type,
        amount=amount,
        balance_before=current_balance,
        balance_after=current_balance + amount if transaction_type == 'deposit' else current_balance - amount,
        investment=investment,
        dividend=dividend,
        description=description,
        metadata=metadata or {},
        status=status,
    )
    
    if investment:
        transaction.metadata['investment_id'] = investment.id
        transaction.metadata['venture_name'] = investment.venture.name
    
    transaction.save()
    return transaction

def send_notification(user, title, message, notification_type='system', 
                     investment=None, venture=None, is_important=False):
    """Send notification to user"""
    notification = Notification(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        investment=investment,
        venture=venture,
        is_important=is_important,
    )
    notification.save()
    
    # Send email for important notifications
    if is_important:
        send_email_notification(user.email, title, message)
    
    return notification

def send_email_notification(email, subject, message):
    """Send email notification"""
    try:
        send_mail(
            subject=f"Airvyb: {subject}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception as e:
        # Log email failure but don't break the app
        print(f"Email send failed: {e}")

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def format_currency(amount):
    """Format currency for display"""
    if amount is None:
        return "Ksh 0.00"
    return f"Ksh {amount:,.2f}"

def calculate_estimated_return(investment, annual_return_rate=0.15):
    """Calculate estimated returns"""
    if not investment or not investment.amount_invested:
        return 0
    
    # Simple calculation - in reality would be more complex
    return investment.amount_invested * annual_return_rate

def validate_investment_amount(amount, venture):
    """Validate investment amount"""
    if amount < venture.minimum_investment:
        return False, f"Minimum investment is {format_currency(venture.minimum_investment)}"
    
    max_amount = venture.available_shares * venture.price_per_share
    if amount > max_amount:
        return False, f"Maximum investment is {format_currency(max_amount)}"
    
    return True, ""

def process_investment_payment(investment, payment_method='mpesa'):
    """Process investment payment (simplified)"""
    # In real app, integrate with payment gateway
    # This is a placeholder for payment processing logic
    
    try:
        # Simulate payment processing
        if payment_method == 'mpesa':
            # Call M-Pesa API
            # payment_response = mpesa_api.stk_push(...)
            payment_success = True  # Placeholder
        else:
            payment_success = False
        
        if payment_success:
            investment.status = 'confirmed'
            investment.confirmed_at = timezone.now()
            investment.save()
            
            # Update venture shares
            venture = investment.venture
            venture.shares_issued += investment.shares
            venture.save()
            
            return True, "Payment successful"
        else:
            return False, "Payment failed"
            
    except Exception as e:
        return False, f"Payment error: {str(e)}"