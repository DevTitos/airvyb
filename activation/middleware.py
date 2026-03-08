from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
import re

class ActivationRequiredMiddleware:
    """
    Middleware that checks if user has active membership
    Redirects to activation page if not active
    Compatible with Django 3.0+
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # URLs that don't require activation check
        self.exempt_urls = [
            reverse('activation:page'),
            reverse('activation:initiate'),
            reverse('activation:callback'),
            reverse('activation:status'),
            reverse('activation:verify_promo'),
            reverse('login'),
            reverse('ajax_logout'),
            reverse('register'),
            #reverse('admin'),
            #reverse('password_reset_done'),
            #reverse('password_reset_confirm'),
            #reverse('password_reset_complete'),
        ]
        
        # Exempt URL patterns using regex
        self.exempt_patterns = [
            r'^/admin/',
            r'^/static/',
            r'^/media/',
            r'^/__debug__/',  # Django Debug Toolbar
        ]
    
    def __call__(self, request):
        # Process the request
        response = self.process_request(request)
        
        # If process_request returns a response, return it immediately
        if response:
            return response
        
        # Otherwise, get the response from the next middleware/view
        return self.get_response(request)
    
    def process_request(self, request):
        """Process the request before the view"""
        # Skip if user is not authenticated
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None
        
        # Skip if URL is exempt
        if request.path in self.exempt_urls:
            return None
        
        # Skip if URL matches exempt patterns
        for pattern in self.exempt_patterns:
            if re.match(pattern, request.path):
                return None
        
        # Check if user has active membership
        try:
            activation = request.user.activation
            if activation.is_active:
                return None  # User is active, continue
            else:
                # User has activation record but not active
                messages.warning(
                    request, 
                    'Please activate your membership to access this page.'
                )
                return redirect('activation:page')
        except (AttributeError, request.user.__class__.activation.RelatedObjectDoesNotExist):
            # User doesn't have activation record
            # Create pending activation record
            from .models import MemberActivation
            MemberActivation.objects.get_or_create(
                user=request.user,
                defaults={'status': 'pending'}
            )
            messages.warning(
                request,
                'Please activate your membership to continue.'
            )
            return redirect('activation:page')
        except Exception as e:
            # Log the error but don't break the site
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Activation middleware error: {str(e)}")
            return None