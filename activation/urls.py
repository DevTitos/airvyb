from django.urls import path
from . import views

app_name = 'activation'

urlpatterns = [
    # Main activation page
    path('', views.activation_page, name='page'),
    
    # Payment initiation
    path('initiate/', views.initiate_activation, name='initiate'),
    
    # M-Pesa callback
    path('callback/', views.activation_callback, name='callback'),
    
    # Status check
    path('status/', views.check_activation_status, name='status'),
    
    # Promo verification
    path('verify-promo/', views.verify_promo, name='verify_promo'),
]